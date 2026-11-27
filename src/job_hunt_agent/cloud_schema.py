"""Cloud/D1 data contract and append-only lifecycle ledger.

This module is deliberately independent of the local SQLite repository.  The
SQL is valid for Cloudflare D1 (SQLite), while the ledger rules are shared by
future API handlers and are safe to exercise locally today.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class LifecycleEvent:
    tenant_id: str
    actor_id: str
    event_type: str
    subject_type: str
    subject_id: str
    payload: dict[str, Any]
    occurred_at: str | None = None

    def validate(self) -> None:
        for name, value in (("tenant_id", self.tenant_id), ("actor_id", self.actor_id),
                            ("event_type", self.event_type), ("subject_type", self.subject_type),
                            ("subject_id", self.subject_id)):
            if not isinstance(value, str) or not ID_RE.fullmatch(value):
                raise ValueError(f"{name} must be a bounded identifier")
        if not isinstance(self.payload, dict):
            raise ValueError("payload must be an object")


class AppendOnlyLedger:
    """Tenant-scoped event writer; no update or delete operation is exposed."""

    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def append(self, event: LifecycleEvent) -> int:
        event.validate()
        cursor = self.connection.execute(
            """INSERT INTO lifecycle_events
               (tenant_id, actor_id, event_type, subject_type, subject_id,
                payload_json, occurred_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (event.tenant_id, event.actor_id, event.event_type, event.subject_type,
             event.subject_id, json.dumps(event.payload, sort_keys=True, separators=(",", ":")),
             event.occurred_at or utc_now()),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def for_subject(self, tenant_id: str, subject_type: str, subject_id: str) -> list[sqlite3.Row]:
        return list(self.connection.execute(
            """SELECT * FROM lifecycle_events
               WHERE tenant_id = ? AND subject_type = ? AND subject_id = ?
               ORDER BY sequence_no""", (tenant_id, subject_type, subject_id)))
