"""Approval-gated, platform-neutral submission handoff preparation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .schemas import JobRecord


@dataclass(frozen=True)
class SubmissionHandoff:
    job_id: str
    platform: str
    source_url: str
    payload: dict[str, object]
    payload_sha256: str
    review_required: bool = True


def prepare_handoff(job: JobRecord, platform: str = "manual-review") -> SubmissionHandoff:
    if not platform.strip():
        raise ValueError("platform is required")
    payload = {"job_id": job.job_id, "title": job.title, "company_name": job.company_name,
               "source_url": job.source_url, "location": job.location, "work_mode": job.work_mode,
               "employment_type": job.employment_type}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return SubmissionHandoff(job.job_id, platform.strip(), job.source_url, payload, hashlib.sha256(encoded).hexdigest())
