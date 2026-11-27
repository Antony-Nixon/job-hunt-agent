from datetime import datetime, timezone

import pytest

from job_hunt_agent.ai_provider import DeterministicProvider
from job_hunt_agent.evidence import inspect_public_link
from job_hunt_agent.storage import Repository


class FakeResponse:
    headers = {"Content-Type": "text/html"}
    def __init__(self): self.done = False
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self, size=-1):
        if self.done: return b""
        self.done = True
        return b"<h1>Automation Engineer</h1> https://example.com/jobs/1"
    def geturl(self): return "https://example.com/jobs/1"


def test_evidence_review_decision_is_audited(tmp_path):
    evidence = inspect_public_link("https://example.com/start", DeterministicProvider(), opener=lambda request, timeout: FakeResponse())
    repo = Repository(tmp_path / "agent.db")
    repo.initialize()
    evidence_id = repo.save_evidence(evidence)
    repo.decide_evidence(evidence_id, "approved", "Public evidence verified")
    row = repo.connection.execute("SELECT decision, note FROM evidence_decisions WHERE evidence_id = ?", (evidence_id,)).fetchone()
    assert tuple(row) == ("approved", "Public evidence verified")
    assert repo.connection.execute("SELECT COUNT(*) FROM events WHERE kind='evidence_review_decision'").fetchone()[0] == 1


def test_evidence_review_rejects_unknown_id(tmp_path):
    repo = Repository(tmp_path / "agent.db")
    repo.initialize()
    with pytest.raises(ValueError, match="unknown evidence_id"):
        repo.decide_evidence("missing", "approved")

