"""Accounts and saved interviews (docs/api.md section 3b).

Plain sqlite3 from the standard library: one file, no extra service. Passwords are hashed with scrypt,
tokens are random and only their SHA-256 hash is stored.
"""

import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from backend.interview.graph import position
from backend.interview.phases import progress

TOKEN_DAYS = 30
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,30}$")
MIN_PASSWORD = 8
TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,      -- stored in lower case
    display_name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tokens (
    token_hash TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS interviews (
    session_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    data TEXT NOT NULL                  -- JSON, see Store.save_interview
);
"""


class AccountError(Exception):
    """`code` is an error code from docs/api.md."""

    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def _now() -> str:
    return datetime.now(timezone.utc).strftime(TIME_FORMAT)


def _scrypt(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)


def _hash_password(password: str) -> str:
    salt = os.urandom(16)
    return f"{salt.hex()}${_scrypt(password, salt).hex()}"


def _check_password(password: str, stored: str) -> bool:
    salt_hex, digest_hex = stored.split("$")
    return hmac.compare_digest(_scrypt(password, bytes.fromhex(salt_hex)), bytes.fromhex(digest_hex))


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class Store:
    def __init__(self, path: Optional[str] = None):
        default = Path(__file__).resolve().parents[2] / "storage" / "app.db"
        self.path = Path(path or os.environ.get("DB_PATH") or default)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._db() as db:
            db.executescript(SCHEMA)

    def _db(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        return db

    # --- users and tokens ---------------------------------------------------------------------

    def register(self, username: str, password: str) -> tuple[str, dict]:
        username = username.strip()
        if not USERNAME_RE.match(username):
            raise AccountError(400, "INVALID_REQUEST", "username: 3-30 characters, letters, digits, _ . -")
        if len(password) < MIN_PASSWORD:
            raise AccountError(400, "INVALID_REQUEST", f"password: at least {MIN_PASSWORD} characters")
        user_id = str(uuid.uuid4())
        try:
            with self._db() as db:
                db.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?)",
                           (user_id, username.lower(), username, _hash_password(password), _now()))
        except sqlite3.IntegrityError:
            raise AccountError(409, "USERNAME_TAKEN", "This username is already taken.")
        return self._new_token(user_id), {"id": user_id, "username": username}

    def login(self, username: str, password: str) -> tuple[str, dict]:
        with self._db() as db:
            row = db.execute("SELECT * FROM users WHERE username = ?", (username.strip().lower(),)).fetchone()
        # Hash even for unknown users, so the answer time does not reveal which usernames exist
        stored = row["password_hash"] if row else _hash_password("unknown-user")
        if not _check_password(password, stored) or row is None:
            raise AccountError(401, "INVALID_CREDENTIALS", "Wrong username or password.")
        return self._new_token(row["id"]), {"id": row["id"], "username": row["display_name"]}

    def _new_token(self, user_id: str) -> str:
        token = secrets.token_urlsafe(32)
        expires = (datetime.now(timezone.utc) + timedelta(days=TOKEN_DAYS)).strftime(TIME_FORMAT)
        with self._db() as db:
            db.execute("DELETE FROM tokens WHERE expires_at < ?", (_now(),))
            db.execute("INSERT INTO tokens VALUES (?, ?, ?)", (_token_hash(token), user_id, expires))
        return token

    def user_for_token(self, token: str) -> Optional[dict]:
        with self._db() as db:
            row = db.execute(
                "SELECT u.id, u.display_name FROM tokens t JOIN users u ON u.id = t.user_id "
                "WHERE t.token_hash = ? AND t.expires_at >= ?", (_token_hash(token), _now())).fetchone()
        return {"id": row["id"], "username": row["display_name"]} if row else None

    def logout(self, token: str) -> None:
        with self._db() as db:
            db.execute("DELETE FROM tokens WHERE token_hash = ?", (_token_hash(token),))

    # --- interviews ---------------------------------------------------------------------------

    def owner(self, session_id: str) -> Optional[str]:
        with self._db() as db:
            row = db.execute("SELECT user_id FROM interviews WHERE session_id = ?", (session_id,)).fetchone()
        return row["user_id"] if row else None

    def save_interview(self, session_id: str, user_id: str, state: dict, turn_feedback: Optional[dict] = None,
                       question_id: Optional[str] = None) -> None:
        """Writes the whole conversation. `turn_feedback` is the feedback for the answer to `question_id`."""
        pos = position(state)
        with self._db() as db:
            row = db.execute("SELECT created_at, data FROM interviews WHERE session_id = ?", (session_id,)).fetchone()
            old = json.loads(row["data"]) if row else {}
            feedback = old.get("turn_feedback", {})
            if turn_feedback and question_id:
                feedback[question_id] = turn_feedback
            data = {
                "language": state["language"], "occupation_id": state["occupation_id"],
                "interviewer_style": state["interviewer_style"], "mode": state["mode"],
                "candidate": state.get("candidate"), "done": bool(state.get("done")),
                "phase": pos.phase, "progress": progress(pos), "history": state.get("transcript", []),
                "current_question_id": (state.get("current_question") or {}).get("id"),
                "turn_feedback": feedback, "report": state.get("report") or old.get("report"),
            }
            now = _now()
            db.execute(
                "INSERT INTO interviews VALUES (?, ?, ?, ?, ?) ON CONFLICT(session_id) DO UPDATE "
                "SET updated_at = excluded.updated_at, data = excluded.data",
                (session_id, user_id, row["created_at"] if row else now, now, json.dumps(data)))

    def list_interviews(self, user_id: str) -> list[dict]:
        with self._db() as db:
            rows = db.execute("SELECT * FROM interviews WHERE user_id = ? ORDER BY updated_at DESC, rowid DESC",
                              (user_id,)).fetchall()
        result = []
        for r in rows:
            d = json.loads(r["data"])
            result.append({"session_id": r["session_id"], "language": d["language"], "occupation_id": d["occupation_id"],
                           "interviewer_style": d["interviewer_style"], "mode": d["mode"],
                           "created_at": r["created_at"], "updated_at": r["updated_at"], "done": d["done"],
                           "overall_score": (d.get("report") or {}).get("overall_score")})
        return result

    def get_interview(self, user_id: str, session_id: str) -> Optional[dict]:
        with self._db() as db:
            r = db.execute("SELECT * FROM interviews WHERE session_id = ? AND user_id = ?",
                           (session_id, user_id)).fetchone()
        if not r:
            return None
        d = json.loads(r["data"])
        feedback = d.get("turn_feedback", {})
        history = [({**t, "turn_feedback": feedback.get(t["question_id"])} if t["role"] == "candidate" else t)
                   for t in d["history"]]
        return {"session_id": session_id, "language": d["language"], "occupation_id": d["occupation_id"],
                "interviewer_style": d["interviewer_style"], "mode": d["mode"], "candidate": d.get("candidate"),
                "created_at": r["created_at"], "done": d["done"], "phase": d["phase"], "progress": d["progress"],
                "current_question_id": d["current_question_id"], "history": history, "report": d.get("report")}
