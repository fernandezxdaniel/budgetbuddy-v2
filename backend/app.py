import os
import re
import sqlite3
from contextlib import closing
from flask import Flask, jsonify, request, send_from_directory
from werkzeug.security import check_password_hash, generate_password_hash
from budget_logic import BudgetError, calculate

try:
    from flask_cors import CORS
except ImportError:
    CORS = None

BASE = os.path.dirname(os.path.abspath(__file__))
FRONTEND = os.path.join(BASE, "..", "frontend")
DB_PATH = os.path.join(BASE, "budgetbuddy.db")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    with closing(db()) as con, con:
        con.execute("""CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL)""")

def fail(msg, code=400):
    return jsonify(ok=False, error=msg), code

def strong(pw):
    return len(pw) >= 8 and re.search(r"[A-Z]", pw) and re.search(r"\d", pw) and re.search(r"[@$!%*?&]", pw)

def create_app():
    app = Flask(__name__)
    if CORS:
        CORS(app, resources={r"/api/*": {"origins": ["http://127.0.0.1:5500", "http://localhost:5500"]}})

    init_db()

    @app.post("/api/signup")
    def signup():
        d = request.get_json(silent=True) or {}
        name, email, pw = str(d.get("name", "")).strip(), str(d.get("email", "")).strip().lower(), str(d.get("password", ""))
        if not name or len(name) > 60:
            return fail("Please enter your name (max 60 characters).")
        if not EMAIL_RE.match(email):
            return fail("Please enter a valid email.")
        if not strong(pw):
            return fail("Password needs 8+ characters, an uppercase letter, a number and a special character (@$!%*?&).")
        try:
            with closing(db()) as con, con:
                con.execute("INSERT INTO users(name,email,password_hash) VALUES(?,?,?)",
                            (name, email, generate_password_hash(pw)))
        except sqlite3.IntegrityError:
            return fail("That email is already registered.", 409)
        return jsonify(ok=True, user={"name": name, "email": email}), 201

    @app.post("/api/login")
    def login():
        d = request.get_json(silent=True) or {}
        email, pw = str(d.get("email", "")).strip().lower(), str(d.get("password", ""))
        with closing(db()) as con:
            row = con.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if not row or not check_password_hash(row["password_hash"], pw):
            return fail("Incorrect email or password.", 401)
        return jsonify(ok=True, user={"name": row["name"], "email": row["email"]})

    @app.post("/api/calculate")
    def api_calculate():
        try:
            return jsonify(calculate(request.get_json(silent=True)))
        except BudgetError as e:
            return fail(str(e))

    @app.get("/api/health")
    def health():
        db_type = "postgresql" if os.getenv("DATABASE_URL") else "sqlite"
        return jsonify(ok=True, database=db_type)

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

if __name__ == "__main__":
    app = create_app()
    app.run(host="127.0.0.1", port=5000, debug=True)


