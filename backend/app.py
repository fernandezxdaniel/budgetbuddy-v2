import os
import re
import secrets
from calendar import monthrange
from datetime import date

from flask import Flask, jsonify, request, send_from_directory
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import check_password_hash, generate_password_hash

from budget_logic import BudgetError, P, calculate, plan_to_json, to_centavos, validate_plan
from database import Database, DuplicateEmail
from segment_tree import SumSegmentTree

try:
    from flask_cors import CORS
except ImportError:
    CORS = None

BASE = os.path.dirname(os.path.abspath(__file__))
FRONTEND = os.path.abspath(os.path.join(BASE, "..", "frontend"))
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
TOKEN_MAX_AGE = 60 * 60 * 24 * 30


def fail(message, code=400):
    return jsonify(ok=False, error=message), code


def strong(password):
    return (
        len(password) >= 8
        and re.search(r"[A-Z]", password)
        and re.search(r"\d", password)
        and re.search(r"[@$!%*?&]", password)
    )


def create_app(database_url=None):
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY") or secrets.token_hex(32)
    database = Database(database_url)
    serializer = URLSafeTimedSerializer(app.config["SECRET_KEY"], salt="budgetbuddy-auth")
    app.extensions["budgetbuddy_database"] = database

    if CORS:
        CORS(app, resources={r"/api/*": {"origins": [
            "http://127.0.0.1:5500", "http://localhost:5500",
        ]}})

    def make_token(user_id):
        return serializer.dumps({"uid": user_id})

    def require_user():
        authorization = request.headers.get("Authorization", "")
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            return None
        try:
            payload = serializer.loads(token, max_age=TOKEN_MAX_AGE)
        except (BadSignature, SignatureExpired):
            return None
        user_id = payload.get("uid") if isinstance(payload, dict) else None
        return database.get_user(user_id)

    def request_today(value=None):
        if value in (None, ""):
            return date.today()
        try:
            return date.fromisoformat(value)
        except (TypeError, ValueError):
            raise BudgetError("Today must be a date (YYYY-MM-DD).")

    def request_period(start_value, end_value):
        if start_value in (None, "") and end_value in (None, ""):
            return None, None
        if start_value in (None, "") or end_value in (None, ""):
            raise BudgetError("Please pick both a start date and an end date.")
        try:
            start = date.fromisoformat(start_value)
            end = date.fromisoformat(end_value)
        except (TypeError, ValueError):
            raise BudgetError("Period dates must use YYYY-MM-DD format.")
        validate_plan({"income": 0, "start": start.isoformat(), "end": end.isoformat(), "items": []})
        return start, end

    def period_income(normalized, user_id):
        if not normalized["start"] or not normalized["end"]:
            normalized["income"] = 0
            return
        normalized["income"] = database.income_total(
            user_id, normalized["start"], normalized["end"]
        )

    def month_start(value, offset):
        index = value.year * 12 + value.month - 1 + offset
        return date(index // 12, index % 12 + 1, 1)

    @app.post("/api/signup")
    def signup():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            data = {}
        name = str(data.get("name", "")).strip()
        email = str(data.get("email", "")).strip().lower()
        password = str(data.get("password", ""))
        if not name or len(name) > 60:
            return fail("Please enter your name (max 60 characters).")
        if len(email) > 254 or not EMAIL_RE.match(email):
            return fail("Please enter a valid email.")
        if not strong(password):
            return fail("Password needs 8+ characters, an uppercase letter, a number and a special character (@$!%*?&).")
        try:
            user_id = database.create_user(name, email, generate_password_hash(password))
        except DuplicateEmail:
            return fail("That email is already registered.", 409)
        return jsonify(
            ok=True,
            token=make_token(user_id),
            user={"name": name, "email": email},
        ), 201

    @app.post("/api/login")
    def login():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            data = {}
        email = str(data.get("email", "")).strip().lower()
        password = str(data.get("password", ""))
        user = database.get_user_by_email(email)
        if not user or not check_password_hash(user["password_hash"], password):
            return fail("Incorrect email or password.", 401)
        return jsonify(
            ok=True,
            token=make_token(user["id"]),
            user={"name": user["name"], "email": user["email"]},
        )

    @app.get("/api/plan")
    def get_plan():
        user = require_user()
        if not user:
            return fail("Please log in again.", 401)
        try:
            today = request_today(request.args.get("today"))
            start, end = request_period(request.args.get("start"), request.args.get("end"))
        except BudgetError as error:
            return fail(str(error))
        normalized = database.load_plan(
            user["id"], start, end, latest=start is None and end is None
        )
        period_income(normalized, user["id"])
        return jsonify(ok=True, plan=plan_to_json(normalized), result=calculate(normalized, today))

    @app.put("/api/plan")
    def put_plan():
        user = require_user()
        if not user:
            return fail("Please log in again.", 401)
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            data = {}
        try:
            normalized = validate_plan(data.get("plan"))
            today = request_today(data.get("today"))
        except BudgetError as error:
            return fail(str(error))
        period_income(normalized, user["id"])
        try:
            normalized = validate_plan(plan_to_json(normalized) | {"income": P(normalized["income"])})
        except BudgetError as error:
            return fail(str(error))
        database.save_plan(user["id"], normalized)
        return jsonify(
            ok=True,
            plan=plan_to_json(normalized),
            result=calculate(normalized, today),
        )

    @app.delete("/api/plan")
    def delete_plan():
        user = require_user()
        if not user:
            return fail("Please log in again.", 401)
        try:
            start, end = request_period(request.args.get("start"), request.args.get("end"))
        except BudgetError as error:
            return fail(str(error))
        if start is None:
            return fail("Choose a dated period before resetting it.")
        deleted = database.delete_period(user["id"], start, end)
        normalized = database.load_plan(user["id"], start, end)
        period_income(normalized, user["id"])
        return jsonify(
            ok=True,
            deleted=deleted,
            plan=plan_to_json(normalized),
            result=calculate(normalized),
        )

    @app.get("/api/income")
    def get_income():
        user = require_user()
        if not user:
            return fail("Please log in again.", 401)
        try:
            start, end = request_period(request.args.get("start"), request.args.get("end"))
        except BudgetError as error:
            return fail(str(error))
        if start is None:
            return fail("Choose a date range to view income.")
        entries = database.list_income(user["id"], start, end)
        return jsonify(
            ok=True,
            income=[{**entry, "amount": P(entry["amount"])} for entry in entries],
            total=P(sum(entry["amount"] for entry in entries)),
        )

    @app.post("/api/income")
    def add_income():
        user = require_user()
        if not user:
            return fail("Please log in again.", 401)
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            data = {}
        try:
            start, end = request_period(data.get("start"), data.get("end"))
            day = request_today(data.get("date"))
            amount = to_centavos(data.get("amount"), "Income")
        except BudgetError as error:
            return fail(str(error))
        if start is None or not start <= day <= end:
            return fail("Income date must be inside the selected date range.")
        if amount <= 0:
            return fail("Income amount must be greater than zero.")
        source = " ".join(str(data.get("source", "")).split()) or "Income"
        if len(source) > 80:
            return fail("Income source must be 80 characters or fewer.")
        entry_id = database.add_income(user["id"], day, amount, source)
        return jsonify(ok=True, id=entry_id), 201

    @app.delete("/api/income/<int:entry_id>")
    def remove_income(entry_id):
        user = require_user()
        if not user:
            return fail("Please log in again.", 401)
        if not database.get_income(user["id"], entry_id):
            return fail("Income entry was not found.", 404)
        if not database.delete_income(user["id"], entry_id):
            return fail("Income entry was not found.", 404)
        return jsonify(ok=True)

    @app.get("/api/analytics")
    def monthly_analytics():
        user = require_user()
        if not user:
            return fail("Please log in again.", 401)
        try:
            today = request_today(request.args.get("today"))
        except BudgetError as error:
            return fail(str(error))
        count = 6
        latest_start = month_start(today, 1 - count)
        start_month = request.args.get("start_month")
        if start_month is None:
            first = latest_start
        else:
            if not re.fullmatch(r"\d{4}-\d{2}", start_month):
                return fail("Start month must use YYYY-MM format.")
            try:
                first = date.fromisoformat(start_month + "-01")
            except ValueError:
                return fail("Start month must use YYYY-MM format.")
            if first > latest_start:
                return fail("Choose a six-month period that ends no later than the current month.")
        last = month_start(first, count)
        end = min(date(last.year, last.month, monthrange(last.year, last.month)[1]), today)
        income_by_day, activity_by_day = database.activity_by_day(user["id"], first, end)
        months = []
        for offset in range(count):
            start = month_start(first, offset)
            month_end = date(start.year, start.month, monthrange(start.year, start.month)[1])
            days = (month_end - start).days + 1
            trees = {key: SumSegmentTree(days) for key in ("income", "needs", "wants", "savings")}
            for day_number in range(days):
                day = date.fromordinal(start.toordinal() + day_number).isoformat()
                trees["income"].update(day_number, income_by_day.get(day, 0))
                for category, amount in activity_by_day.get(day, {}).items():
                    trees[category].update(day_number, amount)
            totals = {key: tree.query(0, days - 1) for key, tree in trees.items()}
            months.append({
                "key": start.strftime("%Y-%m"),
                "label": start.strftime("%B %Y"),
                "income": P(totals["income"]),
                "needs": P(totals["needs"]),
                "wants": P(totals["wants"]),
                "savings": P(totals["savings"]),
                "expenses": P(totals["needs"] + totals["wants"]),
            })
        return jsonify(
            ok=True,
            months=months,
            averages={
                "income": round(sum(month["income"] for month in months) / count, 2),
                "expenses": round(sum(month["expenses"] for month in months) / count, 2),
            },
        )

    @app.get("/api/health")
    def health():
        try:
            database.ping()
        except Exception:
            app.logger.exception("Database health check failed")
            return jsonify(ok=False, database=database.kind), 503
        return jsonify(ok=True, database=database.kind)

    @app.get("/")
    def home():
        return send_from_directory(FRONTEND, "index.html")

    @app.get("/create-account.html")
    def create_account_alias():
        return send_from_directory(FRONTEND, "createaccount.html")

    @app.get("/<path:filename>")
    def frontend_files(filename):
        return send_from_directory(FRONTEND, filename)

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=False)
