"""Password verification and short-lived in-memory browser sessions."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import threading
import time
from collections import defaultdict
from pathlib import Path

from .config import read_json, save_json


ITERATIONS = 600_000
SESSION_LIFETIME = 24 * 60 * 60


def password_record(password: str) -> dict:
    if len(password) < 12:
        raise ValueError("La password deve contenere almeno 12 caratteri")
    salt = secrets.token_bytes(24)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)
    return {
        "algorithm": "pbkdf2-sha256", "iterations": ITERATIONS,
        "salt": base64.b64encode(salt).decode("ascii"),
        "hash": base64.b64encode(digest).decode("ascii"),
    }


class Auth:
    def __init__(self, root: Path):
        self.record = read_json(root / "auth.json")
        if not self.record:
            raise RuntimeError("Password non configurata. Esegui: python -m apphub init")
        self.sessions: dict[str, tuple[float, str]] = {}
        self.attempts: dict[str, list[float]] = defaultdict(list)
        self.lock = threading.Lock()

    def verify(self, password: str) -> bool:
        record = self.record
        if record.get("algorithm") != "pbkdf2-sha256":
            return False
        try:
            salt = base64.b64decode(record["salt"], validate=True)
            expected = base64.b64decode(record["hash"], validate=True)
            iterations = int(record["iterations"])
            if not 100_000 <= iterations <= 2_000_000:
                return False
            digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
            return hmac.compare_digest(expected, digest)
        except (ValueError, KeyError, TypeError):
            return False

    def allow_login(self, address: str) -> bool:
        current = time.monotonic()
        with self.lock:
            attempts = [stamp for stamp in self.attempts[address] if current - stamp < 300]
            if len(attempts) >= 8:
                return False
            attempts.append(current)
            self.attempts[address] = attempts
            return True

    def create_session(self) -> tuple[str, str]:
        token = secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(32)
        with self.lock:
            self.sessions[token] = (time.monotonic() + SESSION_LIFETIME, csrf)
        return token, csrf

    def session(self, token: str | None) -> str | None:
        if not token:
            return None
        with self.lock:
            session = self.sessions.get(token)
            if not session:
                return None
            expires, csrf = session
            if time.monotonic() > expires:
                self.sessions.pop(token, None)
                return None
            return csrf

    def logout(self, token: str | None) -> None:
        with self.lock:
            self.sessions.pop(token or "", None)


def initialize_auth(root: Path, password: str) -> None:
    target = root / "auth.json"
    if target.exists():
        raise RuntimeError("Password già impostata; non sovrascrivo le credenziali esistenti")
    save_json(target, password_record(password))
