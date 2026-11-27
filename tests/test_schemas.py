from datetime import datetime, timezone

import pytest

from job_hunt_agent.schemas import JobRecord, ProfileFact


def test_job_record_accepts_provenance_and_required_fields():
    record = JobRecord(
        job_id="example-1",
        title="Automation Engineer",
        company_name="Example Co",
        source_name="example-board",
        source_url="https://example.com/jobs/1",
        retrieved_at=datetime.now(timezone.utc),
        description="Build reliable workflow automation.",
    )
    record.validate()


def test_job_record_rejects_non_http_source_url():
    record = JobRecord(
        job_id="example-1",
        title="Automation Engineer",
        company_name="Example Co",
        source_name="example-board",
        source_url="file:///local/job",
        retrieved_at=datetime.now(timezone.utc),
        description="Build reliable workflow automation.",
    )
    with pytest.raises(ValueError, match="absolute HTTP or HTTPS"):
        record.validate()


def test_profile_fact_rejects_unbounded_confidence():
    fact = ProfileFact(
        key="skill.python",
        value="Python",
        source="verified-profile",
        verified_at=datetime.now(timezone.utc),
        confidence=1.2,
    )
    with pytest.raises(ValueError, match="between 0.0 and 1.0"):
        fact.validate()

