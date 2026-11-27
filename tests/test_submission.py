from datetime import datetime, timezone

import pytest

from job_hunt_agent.schemas import JobRecord
from job_hunt_agent.storage import Repository
from job_hunt_agent.submission import prepare_handoff


def _job():
    return JobRecord("j1", "Engineer", "Example", "test", "https://example.com/jobs/1", datetime.now(timezone.utc), "Python")


def test_handoff_is_review_only_and_stable():
    handoff = prepare_handoff(_job(), "greenhouse")
    assert handoff.review_required is True
    assert handoff.payload["source_url"] == "https://example.com/jobs/1"
    assert len(handoff.payload_sha256) == 64


def test_handoff_persistence_requires_approved_decision(tmp_path):
    repo = Repository(tmp_path / "agent.db")
    repo.initialize()
    repo.save_job(_job())
    handoff = prepare_handoff(_job())
    with pytest.raises(ValueError, match="approved job decision"):
        repo.save_submission_handoff(handoff.job_id, handoff.platform, handoff.payload, handoff.payload_sha256)
    repo.decide("j1", "approved")
    repo.save_submission_handoff(handoff.job_id, handoff.platform, handoff.payload, handoff.payload_sha256)
    row = repo.connection.execute("SELECT status, payload_sha256 FROM submission_handoffs WHERE job_id='j1'").fetchone()
    assert tuple(row) == ("prepared", handoff.payload_sha256)

