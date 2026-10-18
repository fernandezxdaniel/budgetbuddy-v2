import os
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timezone

import psycopg

DEFAULT_SQLITE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "budgetbuddy.db")


class DuplicateEmail(Exception):
    pass


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Database:
    def __init__(self, url=None):
        self.url = url or os.getenv("DATABASE_URL")
        if self.url and self.url.startswith(("postgres://", "postgresql://")):
            self.url = self.url.replace("postgres://", "postgresql://", 1)
            self.kind = "postgresql"
        else:
            self.kind = "sqlite"
            if self.url and self.url.startswith("sqlite:///"):
                self.path = self.url[len("sqlite:///"):]
            else:
                self.path = DEFAULT_SQLITE
            if self.path != ":memory:":
                os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)

        self._create_tables()

    @contextmanager
    def connect(self):
        """Open one transaction, committing on success and rolling back on error."""
        if self.kind == "sqlite":
            conn = sqlite3.connect(self.path)
            conn.execute("PRAGMA foreign_keys = ON")
        else:
            conn = psycopg.connect(self.url)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _q(self, sql):
        return sql.replace("?", "%s") if self.kind == "postgresql" else sql

    def _create_tables(self):
        pk = "SERIAL PRIMARY KEY" if self.kind == "postgresql" else "INTEGER PRIMARY KEY AUTOINCREMENT"
        statements = [
            f"""CREATE TABLE IF NOT EXISTS users (
                id {pk}, name VARCHAR(60) NOT NULL, email VARCHAR(254) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL, created_at VARCHAR(32) NOT NULL DEFAULT '')""",
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
        with self.connect() as conn:
            cur = conn.cursor()
            for statement in statements:
                cur.execute(statement)
            if self.kind == "sqlite":
                columns = [row[1] for row in cur.execute("PRAGMA table_info(users)").fetchall()]
                if "created_at" not in columns:
                    cur.execute("ALTER TABLE users ADD COLUMN created_at VARCHAR(32) NOT NULL DEFAULT ''")
            else:
                cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at VARCHAR(32) NOT NULL DEFAULT ''")

    def describe(self):
        return {"database": self.kind}

    def ping(self):
        with self.connect() as conn:
            conn.cursor().execute("SELECT 1")

    # ---------- users ----------
    def create_user(self, name, email, password_hash):
        try:
            with self.connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    self._q("INSERT INTO users (name, email, password_hash, created_at) VALUES (?, ?, ?, ?) RETURNING id"),
                    (name, email, password_hash, _now()),
                )
                return cur.fetchone()[0]
        except (sqlite3.IntegrityError, psycopg.IntegrityError) as exc:
            raise DuplicateEmail() from exc

    def _user(self, where, param):
        with self.connect() as conn:
            cur = conn.cursor()
            cur.execute(self._q(
                f"SELECT id, name, email, password_hash FROM users WHERE {where} = ?"
            ), (param,))
            row = cur.fetchone()
        return dict(zip(("id", "name", "email", "password_hash"), row)) if row else None

    def get_user_by_email(self, email):
        return self._user("email", email)

    def get_user(self, uid):
        return self._user("id", uid) if isinstance(uid, int) else None

    # ---------- plan ----------
    def load_plan(self, uid):
        with self.connect() as conn:
            cur = conn.cursor()
            cur.execute(self._q("SELECT income, start_date, end_date FROM plans WHERE user_id = ?"), (uid,))
            plan_row = cur.fetchone()
            cur.execute(self._q(
                "SELECT id, uid, category, name, budget FROM plan_items WHERE user_id = ? ORDER BY sort_order"
            ), (uid,))
            item_rows = cur.fetchall()
            cur.execute(self._q(
                "SELECT l.item_id, l.day, l.amount FROM item_log l "
                "JOIN plan_items i ON i.id = l.item_id WHERE i.user_id = ? ORDER BY l.id"
            ), (uid,))
            logs = {}
            for item_id, day, amount in cur.fetchall():
                logs.setdefault(item_id, []).append((date.fromisoformat(day), amount))
        return {
            "income": plan_row[0] if plan_row else 0,
            "start": date.fromisoformat(plan_row[1]) if plan_row and plan_row[1] else None,
            "end": date.fromisoformat(plan_row[2]) if plan_row and plan_row[2] else None,
            "items": [
                {"uid": row[1], "category": row[2], "name": row[3], "budget": row[4], "log": logs.get(row[0], [])}
                for row in item_rows
            ],
        }

    def save_plan(self, uid, norm):
        """Replace a user's entire plan atomically."""
        with self.connect() as conn:
            cur = conn.cursor()
            cur.execute(self._q(
                "DELETE FROM item_log WHERE item_id IN "
                "(SELECT id FROM plan_items WHERE user_id = ?)"
            ), (uid,))
            cur.execute(self._q("DELETE FROM plan_items WHERE user_id = ?"), (uid,))
            cur.execute(self._q("DELETE FROM plans WHERE user_id = ?"), (uid,))
            cur.execute(self._q(
                "INSERT INTO plans (user_id, income, start_date, end_date, updated_at) VALUES (?, ?, ?, ?, ?)"
            ), (uid, norm["income"], norm["start"].isoformat() if norm["start"] else None,
                norm["end"].isoformat() if norm["end"] else None, _now()))
            for pos, item in enumerate(norm["items"]):
                cur.execute(self._q(
                    "INSERT INTO plan_items (user_id, uid, category, name, budget, sort_order) "
                    "VALUES (?, ?, ?, ?, ?, ?) RETURNING id"
                ), (uid, item["uid"], item["category"], item["name"], item["budget"], pos))
                item_id = cur.fetchone()[0]
                if item["log"]:
                    cur.executemany(self._q(
                        "INSERT INTO item_log (item_id, day, amount) VALUES (?, ?, ?)"
                    ), [(item_id, day.isoformat(), amount) for day, amount in item["log"]])
