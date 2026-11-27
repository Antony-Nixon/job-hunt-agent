"""Tiered retention decisions for evidence and reasoning artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True)
class RetentionPolicy:
    """Durations for temporary material; durable records are never auto-expired."""

    raw_source_days: int = 30
    reasoning_trace_days: int = 7
    low_value_trace_days: int = 2

    def validate(self) -> None:
        if min(self.raw_source_days, self.reasoning_trace_days, self.low_value_trace_days) < 0:
            raise ValueError("retention durations cannot be negative")


def expires_at(kind: str, created_at: datetime, policy: RetentionPolicy = RetentionPolicy()) -> datetime | None:
    """Return expiry for temporary kinds; durable facts/decisions return None."""
    policy.validate()
    durations = {
        "raw_source": policy.raw_source_days,
        "reasoning_trace": policy.reasoning_trace_days,
        "low_value_trace": policy.low_value_trace_days,
    }
    if kind not in durations:
        if kind in {"verified_fact", "decision", "audit_event"}:
            return None
        raise ValueError(f"unknown retention kind: {kind}")
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return created_at + timedelta(days=durations[kind])


def should_expire(kind: str, created_at: datetime, now: datetime | None = None, policy: RetentionPolicy = RetentionPolicy()) -> bool:
    expiry = expires_at(kind, created_at, policy)
    if expiry is None:
        return False
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current >= expiry
