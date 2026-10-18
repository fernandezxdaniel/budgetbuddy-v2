import secrets
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
 
from segment_tree import SumSegmentTree, MaxSegmentTree
from recommendations import generate
 
CATEGORIES = ("needs", "wants", "savings")
RATIOS = {"needs": 50, "wants": 30, "savings": 20}
MAX_AMOUNT = Decimal("1000000000")
MAX_ITEMS, MAX_LOG, MAX_DAYS = 200, 500, 366
 
 
class BudgetError(ValueError):
    """Invalid user input. The message is safe to show to the user."""
 
 
def to_centavos(value, field="amount", signed=False):
    if value is None or isinstance(value, bool):
        raise BudgetError(f"{field} must be a number.")
    try:
        d = Decimal(str(value).replace(",", "").strip())
    except InvalidOperation:
        raise BudgetError(f"{field} must be a number.")
    if not d.is_finite():
        raise BudgetError(f"{field} must be a number.")
    if (d < 0 and not signed) or abs(d) > MAX_AMOUNT:
        raise BudgetError(f"{field} must be between 0 and 1,000,000,000.")
    return int((d * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
 
 
def P(centavos):
    return round(centavos / 100, 2)
 
 
def _fmt(centavos):
    return f"\u20b1{centavos / 100:,.2f}"
 
 
def _date(v, field):
    if v in (None, ""):
        return None
    if not isinstance(v, str):
        raise BudgetError(f"{field} must be a date (YYYY-MM-DD).")
    try:
        return date.fromisoformat(v)
    except ValueError:
        raise BudgetError(f"{field} must be a date (YYYY-MM-DD).")
 
 
def limits(income):
    needs = (income * RATIOS["needs"] + 50) // 100
    wants = (income * RATIOS["wants"] + 50) // 100
    return {"needs": needs, "wants": wants, "savings": income - needs - wants}  # always adds up exactly
 
 
def _div(a, b):
    return (2 * a + b) // (2 * b)          # integer division rounded half up
 
 
# ----------------------------------------------------------------------------------------
def validate_plan(plan):
    """Check everything the user sent and return a clean ("normalized") plan, or raise BudgetError."""
    if not isinstance(plan, dict):
        raise BudgetError("Invalid plan.")
    income = to_centavos(plan.get("income", 0), "Income")
    start, end = _date(plan.get("start"), "Start date"), _date(plan.get("end"), "End date")
    if (start is None) != (end is None):
        raise BudgetError("Please pick both a start date and an end date.")
    if start:
        if end < start:
            raise BudgetError("The end date must be on or after the start date.")
        if (end - start).days + 1 > MAX_DAYS:
            raise BudgetError("The budget period can be at most 366 days.")
 
    raw = plan.get("items", [])
    if not isinstance(raw, list) or len(raw) > MAX_ITEMS:
        raise BudgetError("Too many items (maximum 200).")
    items, names, ids = [], set(), set()
    for it in raw:
        if not isinstance(it, dict):
            raise BudgetError("Each item must be an object.")
        cat = str(it.get("category", "")).strip().lower()
        if cat not in CATEGORIES:
            raise BudgetError("Category must be needs, wants or savings.")
        name = " ".join(str(it.get("name", "")).split())
        if not name or len(name) > 60:
            raise BudgetError("Item names must be 1 to 60 characters.")
        if (cat, name.lower()) in names:
            raise BudgetError(f'"{name}" is already in {cat}.')
        names.add((cat, name.lower()))
        budget = to_centavos(it.get("budget", 0), f'Budget for "{name}"')
        uid = str(it.get("id") or "")[:40]
        if not uid or uid in ids:
            uid = secrets.token_hex(6)
        ids.add(uid)
 
        raw_log = it.get("log", [])
        if not isinstance(raw_log, list) or len(raw_log) > MAX_LOG:
            raise BudgetError(f'Too many entries for "{name}".')
        log, total = [], 0
        for e in raw_log:
            if not isinstance(e, dict):
                raise BudgetError("Each entry must be an object.")
            d = _date(e.get("date"), "Entry date")
            if d is None:
                raise BudgetError("Each entry needs a date.")
            amt = to_centavos(e.get("amount", 0), f'Actual for "{name}"', signed=True)
            log.append((d, amt))
            total += amt
        if total < 0:
            raise BudgetError(f'Actual for "{name}" cannot be negative.')
        items.append({"uid": uid, "category": cat, "name": name, "budget": budget, "log": log})
 
    # The 50/30/20 rule: the budgets of a category may never exceed its limit.
    budgets = {c: sum(i["budget"] for i in items if i["category"] == c) for c in CATEGORIES}
    if income == 0 and any(budgets.values()):
        raise BudgetError("Set income for this period first.")
    lim = limits(income)
    for c in CATEGORIES:
        if budgets[c] > lim[c]:
            raise BudgetError(
                f"{c.title()} budget ({_fmt(budgets[c])}) is over its limit of {_fmt(lim[c])} "
                f"({RATIOS[c]}% of your income). Lower it by {_fmt(budgets[c] - lim[c])}.")
    return {"income": income, "start": start, "end": end, "items": items}
 
 
def plan_to_json(norm):
    return {
        "income": P(norm["income"]),
        "start": norm["start"].isoformat() if norm["start"] else None,
        "end": norm["end"].isoformat() if norm["end"] else None,
        "items": [{"id": it["uid"], "category": it["category"], "name": it["name"], "budget": P(it["budget"]),
                   "log": [{"date": d.isoformat(), "amount": P(a)} for d, a in it["log"]]}
                  for it in norm["items"]],
    }
 
 
# ----------------------------------------------------------------------------------------
def calculate(norm, today=None):
    today = today or date.today()
    income = norm["income"]
    period_set = norm["start"] is not None
    start, end = (norm["start"], norm["end"]) if period_set else (today, today)
    days = (end - start).days + 1
    elapsed = max(0, min(days, (today - start).days + 1))     # days of the period already used
 
    sums = {c: SumSegmentTree(days) for c in CATEGORIES}      # one tree per category
    spend = SumSegmentTree(days)                              # needs + wants per day
    peak = MaxSegmentTree(days)                               # biggest spending day
    day_spend = [0] * days
    budget = {c: 0 for c in CATEGORIES}
    entered = {c: False for c in CATEGORIES}
    rows = {c: [] for c in CATEGORIES}
 
    for it in norm["items"]:
        cat, actual = it["category"], 0
        has_entry = False
        for d, amt in it["log"]:
            if not start <= d <= end:
                continue
            has_entry = True
            idx = (d - start).days
            sums[cat].add(idx, amt)                           # segment-tree point update
            actual += amt
            if cat != "savings":
                spend.add(idx, amt)
                day_spend[idx] += amt
                peak.update(idx, day_spend[idx])
        budget[cat] += it["budget"]
        entered[cat] = entered[cat] or has_entry
        rows[cat].append({"id": it["uid"], "name": it["name"], "budget": P(it["budget"]), "actual": P(actual),
                          "left": P(it["budget"] - actual), "entered": has_entry})
 
    lim = limits(income)
    actual_c = {c: sums[c].query(0, days - 1) for c in CATEGORIES}   # segment-tree range query
    total_budget, total_actual = sum(budget.values()), sum(actual_c.values())
    entered_any = any(entered.values())
 
    spent_total = spend.query(0, days - 1)
    spent_to_date = max(0, spend.query(0, elapsed - 1)) if elapsed else 0
    last7 = max(0, spend.query(max(0, elapsed - 7), elapsed - 1)) if elapsed else 0
    avg = _div(spent_to_date, elapsed) if elapsed else 0
    projected = _div(spent_to_date * days, elapsed) if elapsed else 0
    peak_val = peak.query(0, days - 1)
    peak_idx = day_spend.index(peak_val) if peak_val > 0 else None
    spend_budget = budget["needs"] + budget["wants"]
    spend_left = spend_budget - spent_total
    days_left = days - elapsed
    allowance = 0 if spend_left <= 0 else (spend_left // days_left if days_left > 0 else spend_left)
 
    weekly = []
    for s in range(0, days, 7):
        e = min(s + 6, days - 1)
        weekly.append({"week": len(weekly) + 1, "from": date.fromordinal(start.toordinal() + s).isoformat(),
                       "to": date.fromordinal(start.toordinal() + e).isoformat(), "spent": P(spend.query(s, e))})
 
    result = {
        "ok": True,
        "period": {"set": period_set, "start": start.isoformat(), "end": end.isoformat(), "days": days,
                   "today": today.isoformat(), "elapsed": elapsed, "days_left": days_left,
                   "active": period_set and start <= today <= end},
        "income": P(income),
        "categories": {
            c: {"ratio": RATIOS[c], "limit": P(lim[c]), "budget": P(budget[c]), "actual": P(actual_c[c]),
                "left": P(budget[c] - actual_c[c]), "entered": entered[c], "items": rows[c],
                "percent_used": round(actual_c[c] * 100 / budget[c], 1) if budget[c] else 0.0}
            for c in CATEGORIES},
        "totals": {"budget": P(total_budget), "actual": P(total_actual), "left": P(total_budget - total_actual),
                   "balance": P(income - total_actual), "unallocated": P(income - total_budget)},
        "metrics": {
            "spent_total": P(spent_total), "spent_to_date": P(spent_to_date), "daily_average": P(avg),
            "projected_spending": P(projected), "last_7_days": P(last7), "peak_amount": P(max(peak_val, 0)),
            "peak_day": date.fromordinal(start.toordinal() + peak_idx).isoformat() if peak_idx is not None else None,
            "spending_budget": P(spend_budget), "spending_left": P(spend_left), "daily_allowance": P(allowance)},
        "weekly": weekly,
        "items_count": len(norm["items"]),
        "entered_any": entered_any,
    }
    result["recommendations"] = generate(result)
    return result