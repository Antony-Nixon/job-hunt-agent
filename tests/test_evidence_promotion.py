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


def test_only_approved_evidence_can_be_promoted(tmp_path):
    evidence = inspect_public_link("https://example.com/start", DeterministicProvider(), opener=lambda request, timeout: FakeResponse())
    repo = Repository(tmp_path / "agent.db")
    repo.initialize()
    evidence_id = repo.save_evidence(evidence)
    with pytest.raises(ValueError, match="reviewed"):
        repo.promote_approved_evidence(evidence_id, "j1", "Automation Engineer", "Example Co", "review")
    repo.decide_evidence(evidence_id, "approved")
    assert repo.promote_approved_evidence(evidence_id, "j1", "Automation Engineer", "Example Co", "review") is True
    assert repo.jobs()[0].job_id == "j1"

