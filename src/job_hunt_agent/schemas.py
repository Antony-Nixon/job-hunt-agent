"""Validated, dependency-free domain records used by the local MVP."""

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from typing import Optional
from urllib.parse import urlparse


@dataclass(frozen=True)
class JobRecord:
    """Canonical job record with minimum provenance required for downstream work."""

    job_id: str
    title: str
    company_name: str
    source_name: str
    source_url: str
    retrieved_at: datetime
    description: str
    location: Optional[str] = None
    work_mode: Optional[str] = None
    employment_type: Optional[str] = None
    raw_content_hash: Optional[str] = None
    parser_status: str = "parsed"

    @property
    def content_hash(self) -> str:
        return self.raw_content_hash or sha256(self.description.encode("utf-8")).hexdigest()

    def validate(self) -> None:
        required = {
            "job_id": self.job_id,
            "title": self.title,
            "company_name": self.company_name,
            "source_name": self.source_name,
            "source_url": self.source_url,
            "description": self.description,
        }
        missing = [name for name, value in required.items() if not str(value).strip()]
        if missing:
            raise ValueError(f"Missing required job fields: {', '.join(missing)}")
        parsed = urlparse(self.source_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("source_url must be an absolute HTTP or HTTPS URL")
        if self.parser_status not in {"parsed", "partial", "error"}:
            raise ValueError("parser_status must be parsed, partial, or error")


@dataclass(frozen=True)
class ProfileFact:
    """A candidate fact that can be used in generated material only when sourced."""

    key: str
    value: str
    source: str
    verified_at: datetime
    confidence: float = 1.0

    def validate(self) -> None:
        if not self.key.strip() or not self.value.strip() or not self.source.strip():
            raise ValueError("Profile facts require key, value, and source")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")


@dataclass(frozen=True)
class FitEvaluation:
    """Transparent, evidence-backed fit evaluation."""

    job_id: str
    score: float
    matched_requirements: tuple[str, ...] = ()
    missing_requirements: tuple[str, ...] = ()
    confidence: float = 0.0
    rubric_version: str = "keyword-v1"

    def validate(self) -> None:
        if not 0 <= self.score <= 100 or not 0 <= self.confidence <= 1:
            raise ValueError("score must be 0-100 and confidence must be 0-1")


@dataclass(frozen=True)
class CandidateProfile:
    """Candidate-entered, verified facts and preferences."""

    display_name: str
    facts: tuple[ProfileFact, ...] = ()
    preferred_roles: tuple[str, ...] = ()
    locations: tuple[str, ...] = ()

    def validate(self) -> None:
        if not self.display_name.strip():
            raise ValueError("display_name is required")
        for fact in self.facts:
            fact.validate()
