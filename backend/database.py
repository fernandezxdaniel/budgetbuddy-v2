import os
import sqlite3
import psycopg2
from contextlib import contextmanager
from datetime import date, datetime, timezone

DEFAULT_SQLITE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "budgetbuddy.db")

class DuplicateEmail(Exception):
    pass

def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

class Database:
    def __init__(self, url=None):
        # Use DATABASE_URL if provided, else fallback to SQLite
        self.url = url or os.getenv("DATABASE_URL")
        if self.url and self.url.startswith("postgresql"):
            self.kind = "postgresql"
        else:
            self.kind = "sqlite"
            self.path = DEFAULT_SQLITE

        # Integrity error handling for both backends
        self._INTEGRITY = (sqlite3.IntegrityError,)
        if self.kind == "postgresql":
            self._INTEGRITY += (psycopg2.IntegrityError,)

    def _q(self, sql):
        # Convert ? placeholders to %s for PostgreSQL
        return sql.replace("?", "%s") if self.kind == "postgresql" else sql

    @contextmanager
    def connect(self):
        """One transaction: commit if everything worked, roll back on any error."""
        if self.kind == "sqlite":
            conn = sqlite3.connect(self.path)
            conn.execute("PRAGMA foreign_keys = ON")
        else:
            conn = psycopg2.connect(self.url)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _run(self, conn, sql, params=()):
        return conn.execute(self._q(sql), params)

    def _create_tables(self):
        pk = "SERIAL PRIMARY KEY" if self.kind == "postgresql" else "INTEGER PRIMARY KEY AUTOINCREMENT"
        statements = [
            f"""CREATE TABLE IF NOT EXISTS users (
                id {pk}, name VARCHAR(60) NOT NULL, email VARCHAR(254) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL, created_at VARCHAR(32) NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS plans (
                user_id INTEGER PRIMARY KEY REFERENCES users(id),
                income BIGINT NOT NULL DEFAULT 0 CHECK (income >= 0),
                start_date VARCHAR(10), end_date VARCHAR(10), updated_at VARCHAR(32) NOT NULL)""",
            f"""CREATE TABLE IF NOT EXISTS plan_items (
                id {pk}, user_id INTEGER NOT NULL REFERENCES users(id),
                uid VARCHAR(40) NOT NULL,
                category VARCHAR(10) NOT NULL CHECK (category IN ('needs','wants','savings')),
                name VARCHAR(60) NOT NULL, budget BIGINT NOT NULL CHECK (budget >= 0),
                sort_order INTEGER NOT NULL, UNIQUE (user_id, uid))""",
            "CREATE INDEX IF NOT EXISTS idx_items_user ON plan_items (user_id)",
            f"""CREATE TABLE IF NOT EXISTS item_log (
                id {pk}, item_id INTEGER NOT NULL REFERENCES plan_items(id),
                day VARCHAR(10) NOT NULL, amount BIGINT NOT NULL)""",
            "CREATE INDEX IF NOT EXISTS idx_log_item ON item_log (item_id)",
        ]
        with self.connect() as c:
            cur = c.cursor()
            for s in statements:
                cur.execute(s)
            if self.kind == "sqlite":  # upgrade old database file
                cols = [r[1] for r in cur.execute("PRAGMA table_info(users)").fetchall()]
                if "created_at" not in cols:
                    cur.execute("ALTER TABLE users ADD COLUMN created_at VARCHAR(32) NOT NULL DEFAULT ''")

    def describe(self):
        return {"database": self.kind}

    # ---------- users ----------
    def create_user(self, name, email, password_hash):
        try:
            with self.connect() as c:
                cur = c.cursor()
                cur.execute(
                    self._q("INSERT INTO users (name, email, password_hash, created_at) VALUES (?, ?, ?, ?) RETURNING id"),
                    (name, email, password_hash, _now())
                )
                return cur.fetchone()[0]
        except self._INTEGRITY:
            raise DuplicateEmail()

    def _user(self, where, param):
        with self.connect() as c:
            cur = c.cursor()
            cur.execute(self._q(f"SELECT id, name, email, password_hash FROM users WHERE {where} = ?"), (param,))
            row = cur.fetchone()
        return dict(zip(("id", "name", "email", "password_hash"), row)) if row else None

    def get_user_by_email(self, email):
        return self._user("email", email)

    def get_user(self, uid):
        return self._user("id", uid) if isinstance(uid, int) else None

    # ---------- plan ----------
    def load_plan(self, uid):
        with self.connect() as c:
            cur = c.cursor()
            cur.execute(self._q("SELECT income, start_date, end_date FROM plans WHERE user_id = ?"), (uid,))
            p = cur.fetchone()
            cur.execute(self._q("SELECT id, uid, category, name, budget FROM plan_items WHERE user_id = ? ORDER BY sort_order"), (uid,))
            rows = cur.fetchall()
            cur.execute(self._q("SELECT l.item_id, l.day, l.amount FROM item_log l JOIN plan_items i ON i.id = l.item_id WHERE i.user_id = ? ORDER BY l.id"), (uid,))
            logs = {}
            for item_id, day, amount in cur.fetchall():
                logs.setdefault(item_id, []).append((date.fromisoformat(day), amount))
        return {
            "income": p[0] if p else 0,
            "start": date.fromisoformat(p[1]) if p and p[1] else None,
            "end": date.fromisoformat(p[2]) if p and p[2] else None,
            "items": [{"uid": r[1], "category": r[2], "name": r[3], "budget": r[4], "log": logs.get(r[0], [])}
                      for r in rows],
        }

    def save_plan(self, uid, norm):
        """Replace the user's whole plan in ONE transaction: all saved, or nothing changes."""
        with self.connect() as c:
            cur = c.cursor()
            cur.execute(self._q("DELETE FROM item_log WHERE item_id IN (SELECT id FROM plan_items WHERE user_id = ?)"), (uid,))
            cur.execute(self._q("DELETE FROM plan_items WHERE user_id = ?"), (uid,))
            cur.execute(self._q("DELETE FROM plans WHERE user_id = ?"), (uid,))
            cur.execute(self._q("INSERT INTO plans (user_id, income, start_date, end_date, updated_at) VALUES (?, ?, ?, ?, ?)"),
                        (uid, norm["income"], norm["start"].isoformat() if norm["start"] else None,
                         norm["end"].isoformat() if norm["end"] else None, _now()))
            for pos, it in enumerate(norm["items"]):
                cur.execute(self._q("INSERT INTO plan_items (user_id, uid, category, name, budget, sort_order) VALUES (?, ?, ?, ?, ?, ?) RETURNING id"),
                            (uid, it["uid"], it["category"], it["name"], it["budget"], pos))
                item_id = cur.fetchone()[0]
                if it["log"]:
                    cur.executemany(self._q("INSERT INTO item_log (item_id, day, amount) VALUES (?, ?, ?)"),
                                    [(item_id, d.isoformat(), a) for d, a in it["log"]])
