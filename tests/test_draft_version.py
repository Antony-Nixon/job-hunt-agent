from datetime import datetime, timezone

import pytest

from job_hunt_agent.schemas import JobRecord
from job_hunt_agent.storage import Repository


def test_draft_version_requires_sha256_and_known_job(tmp_path):
    repo = Repository(tmp_path / "agent.db")
    repo.initialize()
    job = JobRecord("j1", "Automation Engineer", "Example Co", "test", "https://example.com/jobs/1", datetime.now(timezone.utc), "Python automation")
    repo.save_job(job)
    digest = "a" * 64
    repo.record_draft_version("j1", "cover_letter", digest)
    assert repo.connection.execute("SELECT COUNT(*) FROM draft_versions").fetchone()[0] == 1
    with pytest.raises(ValueError, match="SHA-256"):
        repo.record_draft_version("j1", "cover_letter", "bad")

