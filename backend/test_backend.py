import os, random, shutil, tempfile
from datetime import date
 
os.environ["SECRET_KEY"] = "test-secret"
TEST_DB_DIR = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(TEST_DB_DIR, "app.db")
from segment_tree import SegmentTree, SumSegmentTree, MaxSegmentTree
from budget_logic import BudgetError, calculate, validate_plan
from database import Database, DuplicateEmail
from app import create_app
 
# ---------------------------------------------------------------- 1. segment tree vs brute force
random.seed(1)
for _ in range(300):
    n = random.randint(1, 40)
    vals = [random.randint(0, 5000) for _ in range(n)]
    s, m = SumSegmentTree(n), MaxSegmentTree(n)
    for i, v in enumerate(vals):
        s.update(i, v); m.update(i, v)
    for _ in range(30):
        i = random.randrange(n); vals[i] = random.randint(0, 5000)
        s.update(i, vals[i]); m.update(i, vals[i])
        a = random.randrange(n); b = random.randrange(a, n)
        assert s.query(a, b) == sum(vals[a:b + 1]) and m.query(a, b) == max(vals[a:b + 1])
assert SegmentTree.from_list([1, 2, 3, 4]).query(1, 3) == 9
 
# ---------------------------------------------------------------- 2. validation + calculation
def mk(income=10000, items=None, start="2026-10-10", end="2026-11-10"):
    return {"income": income, "start": start, "end": end, "items": items or []}
 
def it(cat, name, budget, log=()):
    return {"id": f"{cat}-{name}", "category": cat, "name": name, "budget": budget,
            "log": [{"date": d, "amount": a} for d, a in log]}
 
ITEMS = [
    it("needs", "Rent", 4000, [("2026-10-10", 4000)]),
    it("needs", "Food", 800, [("2026-10-12", 300), ("2026-10-15", 200)]),
    it("needs", "Transportation", 200),
    it("wants", "Online Shopping", 2000, [("2026-10-14", 1500)]),
    it("wants", "Hobbies", 1000),
    it("savings", "Emergency Fund", 1500, [("2026-10-11", 0)]),
    it("savings", "Education Fund", 500),
]
norm = validate_plan(mk(items=ITEMS))
r = calculate(norm, date(2026, 10, 16))
c = r["categories"]
assert (c["needs"]["limit"], c["needs"]["budget"], c["needs"]["actual"], c["needs"]["left"]) == (5000, 5000, 4500, 500)
assert (c["wants"]["limit"], c["wants"]["budget"], c["wants"]["actual"]) == (3000, 3000, 1500)
assert (c["savings"]["limit"], c["savings"]["budget"], c["savings"]["actual"]) == (2000, 2000, 0)
by = {i["name"]: i for cat in c.values() for i in cat["items"]}
assert by["Transportation"]["entered"] is False          # Left must stay hidden until an Actual is entered
assert by["Emergency Fund"]["entered"] is True           # an explicit 0.00 counts as entered
assert r["totals"] == {"budget": 10000, "actual": 6000, "left": 4000, "balance": 4000, "unallocated": 0}
p, m = r["period"], r["metrics"]
assert (p["days"], p["elapsed"], p["days_left"]) == (32, 7, 25)
assert m["spent_total"] == m["spent_to_date"] == m["last_7_days"] == 6000
assert m["daily_average"] == 857.14 and m["projected_spending"] == 27428.57
assert m["peak_day"] == "2026-10-10" and m["peak_amount"] == 4000 and m["daily_allowance"] == 80.0
assert len(r["weekly"]) == 5 and sum(w["spent"] for w in r["weekly"]) == 6000
assert any("on pace" in x["title"] for x in r["recommendations"])
before = calculate(norm, date(2026, 10, 1))["period"]; assert before["elapsed"] == 0
after = calculate(norm, date(2026, 12, 1))["period"];  assert (after["elapsed"], after["days_left"]) == (32, 0)
assert r["period"]["active"] is True
for days in (1, 2, 3, 90, 366):
    end_day = date(2026, 1, 1).toordinal() + days - 1
    end_date = date.fromordinal(end_day).isoformat()
    period_result = calculate(validate_plan(mk(start="2026-01-01", end=end_date)), date(2026, 1, 2))
    assert period_result["period"]["days"] == days
    assert period_result["categories"]["needs"]["limit"] == 5000
    assert all(isinstance(rec["message"], str) for rec in period_result["recommendations"])
outside_log = validate_plan(mk(items=[it("needs", "Rent", 100, [("2026-09-01", 50)])]))
assert outside_log["items"][0]["log"][0][0] == date(2026, 9, 1)
assert calculate(outside_log, date(2026, 10, 16))["categories"]["needs"]["actual"] == 0
below_rule_limit = validate_plan(mk(items=[it("needs", "Rent", 1000, [("2026-10-10", 1500)])]))
below_recommendations = calculate(below_rule_limit, date(2026, 10, 16))["recommendations"]
assert any(x["title"] == "Needs exceeded the planned budget" for x in below_recommendations)
assert not any(x["title"] == "Needs exceeded the 50% target" for x in below_recommendations)
above_rule_limit = validate_plan(mk(items=[it("needs", "Rent", 1000, [("2026-10-10", 6000)])]))
assert any(x["title"] == "Needs exceeded the 50% target"
           for x in calculate(above_rule_limit, date(2026, 10, 16))["recommendations"])
 
BAD = [
    (mk(items=[it("needs", "Rent", 5000.01)]), "over its limit"),
    (mk(income=8000, items=ITEMS), "over its limit"),                 # lowering income below existing budgets
    (mk(income=0, items=[it("needs", "Rent", 1)]), "income for this period first"),
    (mk(items=[it("needs", "Rent", 100, [("2026-10-10", -1)])]), "negative"),
    (mk(items=[it("needs", "Rent", 100), it("needs", "rent", 50)]), "already"),
    (mk(end=None), "both"), (mk(start="2026-11-10", end="2026-10-10"), "end date"),
    (mk(start="2026-01-01", end="2027-12-31"), "366"), (mk(items=[it("food", "Rent", 1)]), "Category"),
    (mk(income="abc"), "number"), (mk(start="notadate"), "date"),
]
for plan, text in BAD:
    try:
        validate_plan(plan); raise SystemExit(f"should have failed: {plan}")
    except BudgetError as e:
        assert text in str(e), (text, str(e))
e = calculate(validate_plan(mk(income=0)), date(2026, 10, 16))
assert e["recommendations"][0]["title"].startswith("Set income for this period")
none = calculate(validate_plan({"income": 1000}), date(2026, 10, 16)); assert none["period"]["set"] is False
 
# ---------------------------------------------------------------- 3. database: saved, reloaded, replaced
tmp = tempfile.mkdtemp()
url = "sqlite:///" + os.path.join(tmp, "t.db")
db = Database(url)
uid = db.create_user("Ana", "a@x.com", "hash")
try:
    db.create_user("Ana2", "a@x.com", "hash"); raise SystemExit("duplicate email accepted")
except DuplicateEmail:
    pass
assert db.load_plan(uid)["items"] == []
db.save_plan(uid, norm)
assert Database(url).load_plan(uid) == norm               # a brand-new connection still sees it: it was SAVED
smaller = validate_plan(mk(items=ITEMS[:2]))
db.save_plan(uid, smaller); assert db.load_plan(uid) == smaller
november = validate_plan(mk(income=12000, start="2026-11-01", end="2026-11-30",
                            items=[it("needs", "Rent", 5000, [("2026-11-10", 1200)])]))
db.save_plan(uid, november)
assert db.load_plan(uid, smaller["start"], smaller["end"]) == smaller
assert db.load_plan(uid, november["start"], november["end"]) == november
 
# an old database file (first version: no created_at column, one existing account) must keep working
import sqlite3
old = os.path.join(tmp, "old.db")
con = sqlite3.connect(old)
con.execute("CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL)")
con.execute("INSERT INTO users (name, email, password_hash) VALUES ('Old', 'old@x.com', 'h')"); con.commit(); con.close()
con = sqlite3.connect(old)
con.execute("CREATE TABLE plans (user_id INTEGER PRIMARY KEY, income INTEGER, start_date TEXT, end_date TEXT, updated_at TEXT)")
con.execute("INSERT INTO plans VALUES (1, 1000000, '2026-10-01', '2026-10-30', '2026-10-01T00:00:00Z')")
con.execute("CREATE TABLE plan_items (id INTEGER PRIMARY KEY, user_id INTEGER, uid TEXT, category TEXT, name TEXT, budget INTEGER, sort_order INTEGER)")
con.execute("INSERT INTO plan_items VALUES (1, 1, 'old-rent', 'needs', 'Rent', 400000, 0)")
con.execute("CREATE TABLE item_log (id INTEGER PRIMARY KEY, item_id INTEGER, day TEXT, amount INTEGER)")
con.execute("INSERT INTO item_log VALUES (1, 1, '2026-10-10', 120000)")
con.commit(); con.close()
dbo = Database("sqlite:///" + old)
assert dbo.get_user_by_email("old@x.com")["name"] == "Old"
assert dbo.create_user("New", "new@x.com", "h") > 1
legacy = dbo.load_plan(1, date(2026, 10, 1), date(2026, 10, 30))
assert legacy["income"] == 1000000 and legacy["items"][0]["log"] == [(date(2026, 10, 10), 120000)]
legacy_income = dbo.list_income(1, date(2026, 10, 1), date(2026, 10, 30))
assert len(legacy_income) == 1 and legacy_income[0]["amount"] == 1000000
Database("sqlite:///" + old)
assert len(Database("sqlite:///" + old).list_income(1, date(2026, 10, 1), date(2026, 10, 30))) == 1
assert dbo.delete_period(1, date(2026, 10, 1), date(2026, 10, 30))
assert Database("sqlite:///" + old).load_plan(1, date(2026, 10, 1), date(2026, 10, 30))["items"] == []
 
# ---------------------------------------------------------------- 4. the whole API
client = create_app("sqlite:///" + os.path.join(tmp, "api.db")).test_client()
j = lambda resp: resp.get_json()
s = client.post("/api/signup", json={"name": "Juan", "email": "J@x.com", "password": "Abcdef1!"})
assert s.status_code == 201 and j(s)["token"], "signup must sign the user in"
H = {"Authorization": "Bearer " + j(s)["token"]}
assert client.post("/api/signup", json={"name": "J", "email": "j@x.com", "password": "Abcdef1!"}).status_code == 409
assert client.post("/api/signup", json={"name": "J", "email": "bad", "password": "Abcdef1!"}).status_code == 400
assert client.post("/api/signup", json={"name": "J", "email": "k@x.com", "password": "weak"}).status_code == 400
assert client.post("/api/login", json={"email": "j@x.com", "password": "bad"}).status_code == 401
assert client.post("/api/login", json={"email": "j@x.com", "password": "Abcdef1!"}).status_code == 200
assert client.get("/api/plan").status_code == 401
assert client.get("/api/plan", headers={"Authorization": "Bearer abc"}).status_code == 401
g = j(client.get("/api/plan?today=2026-10-16", headers=H))
assert g["plan"]["items"] == [] and g["result"]["recommendations"][0]["title"].startswith("Set income")
oct_income = client.post("/api/income", headers=H, json={
    "start": "2026-10-10", "end": "2026-11-10",
    "date": "2026-10-15", "amount": 10000, "source": "Paycheck",
})
assert oct_income.status_code == 201
october_range = j(client.get(
    "/api/income?start=2026-10-01&end=2026-10-31", headers=H
))
assert october_range["total"] == 10000 and october_range["income"][0]["date"] == "2026-10-15"
assert client.post("/api/income", headers=H, json={
    "start": "2026-10-10", "end": "2026-11-10",
    "date": "2026-11-15", "amount": 100, "source": "Outside range",
}).status_code == 400
put = client.put("/api/plan", headers=H, json={"plan": mk(items=ITEMS), "today": "2026-10-16"})
assert put.status_code == 200 and j(put)["result"]["categories"]["needs"]["actual"] == 4500
assert j(client.get("/api/plan?today=2026-10-16", headers=H))["plan"] == j(put)["plan"]
nov_income = client.post("/api/income", headers=H, json={
    "start": "2026-11-01", "end": "2026-11-30",
    "date": "2026-11-11", "amount": 12000, "source": "November pay",
})
assert nov_income.status_code == 201
november_plan = mk(income=12000, start="2026-11-01", end="2026-11-30",
                   items=[it("needs", "Rent", 5000, [("2026-11-10", 1200)])])
nov_put = client.put("/api/plan", headers=H, json={"plan": november_plan, "today": "2026-11-12"})
assert nov_put.status_code == 200
Database("sqlite:///" + os.path.join(tmp, "api.db"))
assert j(client.get("/api/income?start=2026-11-01&end=2026-11-30", headers=H))["total"] == 12000
oct_get = client.get("/api/plan?start=2026-10-10&end=2026-11-10&today=2026-11-12", headers=H)
assert j(oct_get)["plan"] == j(put)["plan"]
nov_get = client.get("/api/plan?start=2026-11-01&end=2026-11-30&today=2026-11-12", headers=H)
assert j(nov_get)["plan"] == j(nov_put)["plan"]
trend = j(client.get("/api/analytics?today=2026-11-12", headers=H))
assert len(trend["months"]) == 6
assert [m["expenses"] for m in trend["months"][-2:]] == [6000, 1200]
assert [m["income"] for m in trend["months"][-2:]] == [10000, 12000]
assert trend["averages"]["expenses"] == 1200
assert client.delete("/api/plan?start=2026-11-01&end=2026-11-30", headers=H).status_code == 200
assert j(client.get("/api/plan?start=2026-10-10&end=2026-11-10&today=2026-11-12", headers=H))["plan"] == j(put)["plan"]
bad_plan = mk(start="2026-10-10", end="2026-11-10", items=[it("needs", "Rent", 6000)])
bad = client.put("/api/plan", headers=H, json={"plan": bad_plan, "today": "2026-10-16"})
assert bad.status_code == 400 and "over its limit" in j(bad)["error"]
assert j(client.get("/api/plan?start=2026-10-10&end=2026-11-10&today=2026-10-16", headers=H))["plan"] == j(put)["plan"], "a rejected save must change nothing"
t2 = j(client.post("/api/signup", json={"name": "Ben", "email": "b@x.com", "password": "Abcdef1!"}))["token"]
assert j(client.get("/api/plan", headers={"Authorization": "Bearer " + t2}))["plan"]["items"] == []
assert client.delete("/api/income/" + str(j(oct_income)["id"]),
                     headers={"Authorization": "Bearer " + t2}).status_code == 404
h = j(client.get("/api/health")); assert h["ok"] and h["database"] == "sqlite"
assert client.get("/").status_code == 200
assert client.get("/create-account.html").status_code == 200
 
shutil.rmtree(tmp, ignore_errors=True)
shutil.rmtree(TEST_DB_DIR, ignore_errors=True)
print("ALL TESTS PASSED")
for x in r["recommendations"]:
    print("-", x["level"], "|", x["title"])
