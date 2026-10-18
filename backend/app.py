import os
import re
import secrets
from datetime import date

from flask import Flask, jsonify, request, send_from_directory
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import check_password_hash, generate_password_hash

from budget_logic import BudgetError, calculate, plan_to_json, validate_plan
from database import Database, DuplicateEmail

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
        except BudgetError as error:
            return fail(str(error))
        normalized = database.load_plan(user["id"])
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
        database.save_plan(user["id"], normalized)
        return jsonify(
            ok=True,
            plan=plan_to_json(normalized),
            result=calculate(normalized, today),
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
