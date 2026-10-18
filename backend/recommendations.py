"""recommendations.py - student-friendly advice built from the calculation result."""
import math
from datetime import date

_ORDER = {"danger": 0, "warning": 1, "info": 2, "good": 3}


def peso(x):
    return f"\u20b1{x:,.2f}"


def _r(level, title, message):
    return {"level": level, "title": title, "message": message}


def generate(r):
    inc, cats, m, per = r["income"], r["categories"], r["metrics"], r["period"]
    if inc <= 0:
        return [_r("info", "Set your monthly income first",
                   "Click the Income card on the dashboard and enter your allowance or earnings. "
                   "BudgetBuddy uses the 50/30/20 rule: 50% needs, 30% wants, 20% savings.")]
    if r["items_count"] == 0:
        return [_r("info", "Start logging your spending",
                   f"With {peso(inc)} a month, your plan is {peso(cats['needs']['budget'])} for needs, "
                   f"{peso(cats['wants']['budget'])} for wants and {peso(cats['savings']['budget'])} for savings. "
                   "Add every expense when you spend it so the numbers stay accurate.")]

    out, n, w, s = [], cats["needs"], cats["wants"], cats["savings"]
    spend_left = m["spending_left"]

    if r["totals"]["balance"] < 0:
        out.append(_r("danger", "You are spending more than you receive",
                      f"You are {peso(-r['totals']['balance'])} over your income. Stop non-essential "
                      "purchases now, and talk to family or look for extra income (tutoring, freelance, "
                      "part-time) before borrowing."))
    if n["left"] < 0:
        out.append(_r("warning", "Needs are over your 50% plan",
                      f"You spent {peso(-n['left'])} more than your {peso(n['budget'])} needs budget. "
                      "Trim food and transport first: cook or meal-prep, buy from public markets, share "
                      "bills with roommates, and pause unused subscriptions. If needs stay above 50%, "
                      "cut wants before touching savings."))
    if w["left"] < 0:
        out.append(_r("warning", "Wants are over your 30% plan",
                      f"You are {peso(-w['left'])} over your {peso(w['budget'])} wants budget. Try a "
                      "24-hour rule before buying, use student discounts, and choose free campus or "
                      "community activities for the rest of the month."))
    elif w["budget"] > 0 and w["percent_used"] >= 80:
        out.append(_r("info", "Wants are almost used up",
                      f"You used {w['percent_used']}% of your wants budget and only {peso(w['left'])} is left."))

    if s["actual"] == 0:
        out.append(_r("warning", "You have not saved anything yet",
                      f"Pay yourself first: move even \u20b150 a day into savings as soon as your allowance "
                      f"arrives. Your goal this month is {peso(s['budget'])}."))
    elif s["left"] > 0:
        if per["days_left"] > 0:
            per_day = math.ceil(s["left"] / per["days_left"])
            tip = f"Setting aside about {peso(per_day)} a day for the remaining {per['days_left']} days reaches it."
        else:
            tip = "The month is ending, so carry the gap into next month's plan."
        out.append(_r("info", "Savings goal is not reached yet",
                      f"You still need {peso(s['left'])} to hit your {peso(s['budget'])} target. {tip}"))
    else:
        out.append(_r("good", "Savings goal reached",
                      f"You saved {peso(s['actual'])}, meeting your {peso(s['budget'])} target. Keep it in "
                      f"a separate account. An emergency fund of about {peso(n['budget'] * 3)} "
                      "(3 months of needs) is a great next target."))

    if m["projected_spending"] > m["spending_budget"] and spend_left >= 0:
        msg = (f"At your current pace you will spend about {peso(m['projected_spending'])} this month, "
               f"above your {peso(m['spending_budget'])} limit for needs and wants.")
        if m["daily_allowance"] > 0:
            msg += f" Keep each remaining day under {peso(m['daily_allowance'])} to stay on plan."
        out.append(_r("warning", "You are on pace to overspend", msg))

    spent = m["spent_total"]
    if m["peak_day"] and spent > 0 and date.fromisoformat(per["today"]).day >= 5 and m["peak_amount"] / spent >= 0.4:
        out.append(_r("info", f"One day drove your spending (day {m['peak_day']})",
                      f"{peso(m['peak_amount'])} was {round(m['peak_amount'] / spent * 100)}% of everything "
                      "you spent. Plan big purchases ahead and spread them across the month."))

    big = r.get("largest_expense")
    if big and big["amount"] >= 0.3 * inc:
        out.append(_r("info", "Your biggest expense",
                      f"\"{big['name']}\" ({peso(big['amount'])}) is {round(big['amount'] / inc * 100)}% of "
                      "your income. Check if there is a cheaper option."))

    if not any(x["level"] in ("danger", "warning") for x in out):
        out.append(_r("good", "You are on track",
                      f"Needs and wants are within plan and you still have {peso(max(spend_left, 0))} of "
                      "spending room. Any leftover at month end is best moved to savings."))

    out.sort(key=lambda x: _ORDER[x["level"]])   # stable: danger first, good last
    return out[:6]
