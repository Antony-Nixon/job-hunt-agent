import pytest

from job_hunt_agent.schemas import JobRecord
from job_hunt_agent.storage import Repository


def test_draft_decision_is_validated_and_audited(tmp_path):
    repo = Repository(tmp_path / "agent.db")
    repo.initialize()
    job = JobRecord("j1", "Automation Engineer", "Example Co", "test", "https://example.com/jobs/1", __import__("datetime").datetime.now(__import__("datetime").timezone.utc), "Python automation")
    repo.save_job(job)
    repo.decide_draft("j1", "cover_letter", "approved", "Reviewed")
    row = repo.connection.execute("SELECT decision, note FROM draft_decisions WHERE job_id='j1'").fetchone()
    assert tuple(row) == ("approved", "Reviewed")
    with pytest.raises(ValueError, match="invalid draft type"):
        repo.decide_draft("j1", "unknown", "approved")
