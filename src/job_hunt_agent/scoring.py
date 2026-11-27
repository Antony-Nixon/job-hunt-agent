"""Transparent, deterministic initial scoring; no model calls or hidden inference."""

import re
from .schemas import FitEvaluation, JobRecord, ProfileFact


def _terms(value: str) -> set[str]:
    return {word.lower() for word in re.findall(r"[A-Za-z][A-Za-z0-9+#.-]{1,}", value)}


def evaluate(job: JobRecord, facts: list[ProfileFact], preferred_roles: tuple[str, ...] = ()) -> FitEvaluation:
    job.validate()
    fact_terms = {term for fact in facts if fact.confidence >= 0.8 for term in _terms(fact.value)}
    job_terms = _terms(f"{job.title} {job.description}")
    required = {term for term in job_terms if term in {"python", "sql", "salesforce", "hubspot", "automation", "api", "aws", "javascript", "crm", "selenium", "rpa", "cloudflare", "erp", "pwa", "bash", "revops", "telegram"}}
    matched = tuple(sorted(required & fact_terms))
    missing = tuple(sorted(required - fact_terms))
    role_match = any(role.lower() in job.title.lower() for role in preferred_roles)
    coverage = len(matched) / max(1, len(required))
    score = min(100.0, round((coverage * 75) + (25 if role_match else 0), 1))
    confidence = min(1.0, round((len(matched) + (1 if role_match else 0)) / 8, 2))
    return FitEvaluation(job.job_id, score, matched, missing, confidence)
