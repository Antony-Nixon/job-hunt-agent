from datetime import datetime, timedelta, timezone

from job_hunt_agent.ai_provider import DeterministicProvider
from job_hunt_agent.evidence import inspect_public_link
from job_hunt_agent.schemas import JobRecord
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


def test_evidence_is_persisted_and_expired_without_losing_audit(tmp_path):
    evidence = inspect_public_link("https://example.com/start", DeterministicProvider(), opener=lambda request, timeout: FakeResponse())
    repo = Repository(tmp_path / "agent.db")
    repo.initialize()
    evidence_id = repo.save_evidence(evidence)
    assert evidence_id
    assert repo.purge_expired_evidence(datetime.now(timezone.utc) + timedelta(days=31)) == 1
    assert repo.connection.execute("SELECT COUNT(*) FROM evidence").fetchone()[0] == 0
    assert repo.connection.execute("SELECT COUNT(*) FROM events WHERE kind='evidence_expired'").fetchone()[0] == 1


def test_structured_fields_and_recovery_category_are_persisted(tmp_path):
    evidence = inspect_public_link("https://example.com/start", DeterministicProvider(), opener=lambda request, timeout: FakeResponse())
    evidence = evidence.__class__(**{**evidence.__dict__, "structured_fields": {"title": "Example"}, "error_category": "network"})
    repo = Repository(tmp_path / "agent.db")
    repo.initialize()
    evidence_id = repo.save_evidence(evidence)
    row = repo.connection.execute("SELECT structured_json, error_category, provider_name, provider_model FROM evidence WHERE evidence_id = ?", (evidence_id,)).fetchone()
    assert row[0] == '{"title": "Example"}'
    assert row[1] == "network"
    assert row[2:] == ("deterministic", "rules-v1")


def test_application_stats_are_lifecycle_counts(tmp_path):
    repo = Repository(tmp_path / "agent.db")
    repo.initialize()
    repo.save_job(JobRecord("j1", "Engineer", "Example", "test", "https://example.com/jobs/1", datetime.now(timezone.utc), "Python"))
    repo.application("j1", "review_required")
    try:
        repo.application("j2", "interview")
    except ValueError as exc:
        assert str(exc) == "unknown job_id"
    else:
        raise AssertionError("unknown applications should be rejected")
    stats = repo.application_stats()
    assert stats["total"] == 1
    assert stats["review_required"] == 1


def test_submitted_status_requires_explicit_job_approval(tmp_path):
    repo = Repository(tmp_path / "agent.db")
    repo.initialize()
    repo.save_job(JobRecord("j1", "Engineer", "Example", "test", "https://example.com/jobs/1", datetime.now(timezone.utc), "Python"))
    try:
        repo.application("j1", "submitted")
    except ValueError as exc:
        assert "approved job decision" in str(exc)
    else:
        raise AssertionError("submission status must require approval")
    repo.decide("j1", "approved")
    repo.application("j1", "submitted")
    assert repo.application_stats()["submitted"] == 1


def test_integrity_report_is_clean_for_canonical_records(tmp_path):
    repo = Repository(tmp_path / "agent.db")
    repo.initialize()
    repo.save_job(JobRecord("j1", "Engineer", "Example", "test", "https://example.com/jobs/1", datetime.now(timezone.utc), "Python"))
    repo.application("j1", "review_required")
    assert repo.integrity_report()["total_issues"] == 0

