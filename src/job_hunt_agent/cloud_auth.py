"""Provider-neutral, server-side session primitives for the hosted API.

The future Worker may replace token issuance with an OAuth provider, but the
API-facing contract remains the same: only a hash is stored, sessions expire,
and revocation is explicit. Raw bearer tokens are never persisted or logged.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SessionIdentity:
    user_id: str
    tenant_id: str
    session_id: str


class SessionStore:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def issue(self, user_id: str, tenant_id: str, ttl: timedelta = timedelta(days=7)) -> str:
        if ttl.total_seconds() <= 0 or ttl > timedelta(days=30):
            raise ValueError("session ttl must be positive and at most 30 days")
        user = self.connection.execute(
            "SELECT 1 FROM users WHERE user_id = ? AND tenant_id = ?", (user_id, tenant_id)
        ).fetchone()
        if not user:
            raise ValueError("unknown tenant user")
        token = secrets.token_urlsafe(32)
        session_id = secrets.token_hex(16)
        created = _now()
        self.connection.execute(
            """INSERT INTO sessions
               (session_id, user_id, tenant_id, token_hash, created_at, expires_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (session_id, user_id, tenant_id, _hash(token), created.isoformat(), (created + ttl).isoformat()),
        )
        self.connection.commit()
        return token

    def resolve(self, token: str, now: datetime | None = None) -> SessionIdentity | None:
        if not token or len(token) > 256:
            return None
        row = self.connection.execute(
            """SELECT session_id, user_id, tenant_id, expires_at, revoked_at
               FROM sessions WHERE token_hash = ?""", (_hash(token),)
        ).fetchone()
        if not row or row["revoked_at"]:
            return None
        if datetime.fromisoformat(row["expires_at"]) <= (now or _now()):
            return None
        return SessionIdentity(row["user_id"], row["tenant_id"], row["session_id"])

    def revoke(self, token: str) -> bool:
        cursor = self.connection.execute(
            "UPDATE sessions SET revoked_at = ? WHERE token_hash = ? AND revoked_at IS NULL",
            (_now().isoformat(), _hash(token)),
        )
        self.connection.commit()
        return cursor.rowcount == 1

