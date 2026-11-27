"""Small tenant-scoped service layer for the future hosted API.

The service intentionally contains no authentication implementation yet. A
future Worker will authenticate a request, construct a TenantContext, and
delegate here. Keeping ownership checks in this layer prevents route handlers
from accidentally issuing unscoped queries.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any

from .cloud_schema import AppendOnlyLedger, LifecycleEvent, utc_now


@dataclass(frozen=True)
class TenantContext:
    tenant_id: str
    actor_id: str


class CloudService:
    def __init__(self, connection: sqlite3.Connection, context: TenantContext):
        if not context.tenant_id or not context.actor_id:
            raise ValueError("tenant and actor context are required")
        self.connection = connection
        self.context = context
        self.ledger = AppendOnlyLedger(connection)

    def timeline(self, subject_type: str, subject_id: str) -> list[sqlite3.Row]:
        return self.ledger.for_subject(self.context.tenant_id, subject_type, subject_id)

    def jobs(self) -> list[sqlite3.Row]:
        return list(self.connection.execute(
            "SELECT * FROM jobs WHERE tenant_id = ? ORDER BY created_at DESC",
            (self.context.tenant_id,),
        ))

    def create_job(self, job: dict[str, Any]) -> None:
        required = ("job_id", "title", "company_name", "source_name", "source_url", "description", "raw_content_hash")
        if any(not isinstance(job.get(key), str) or not job[key] for key in required):
            raise ValueError("job fields are required")
        self.connection.execute(
            """INSERT INTO jobs
               (tenant_id, job_id, title, company_name, source_name, source_url,
                description, raw_content_hash, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (self.context.tenant_id, *(job[key] for key in required), utc_now()),
        )
        self.connection.commit()
        self.ledger.append(LifecycleEvent(
            self.context.tenant_id, self.context.actor_id, "discovered", "job",
            job["job_id"], {"source_name": job["source_name"]},
        ))
