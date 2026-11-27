from datetime import datetime, timezone

from job_hunt_agent.cli import _catalog_status
from job_hunt_agent.cli import _fetch_catalog_entry, _load_catalog, _score_status
from job_hunt_agent.schemas import FitEvaluation
from job_hunt_agent.schemas import JobRecord
from job_hunt_agent.storage import Repository


def test_catalog_status_reports_stored_and_reviewed_board_jobs(tmp_path):
    repo = Repository(tmp_path / "agent.db")
    repo.initialize()
    job = JobRecord("j1", "Automation Engineer", "Example", "ashby", "https://jobs.ashbyhq.com/acme/1", datetime.now(timezone.utc), "Python")
    repo.save_job(job)
    repo.decide("j1", "deferred", "review later")
    report = _catalog_status([{"name": "Acme", "provider": "ashby", "board": "acme", "enabled": True}], repo)
    assert report["boards"][0]["stored_jobs"] == 1
    assert report["boards"][0]["reviewed_jobs"] == 1
    assert report["boards"][0]["decisions"]["deferred"] == 1


def test_catalog_loader_rejects_unsupported_provider(tmp_path):
    catalog = tmp_path / "boards.json"
    catalog.write_text('[{"provider":"unknown","board":"x"}]', encoding="utf-8")
    try:
        _load_catalog(catalog)
    except SystemExit as exc:
        assert "Invalid board catalog" in str(exc)
    else:
        raise AssertionError("unsupported provider should be rejected")


def test_score_status_reports_unscored_and_score_bands(tmp_path):
    repo = Repository(tmp_path / "agent.db")
    repo.initialize()
    job = JobRecord("j1", "Automation Engineer", "Example", "ashby", "https://jobs.ashbyhq.com/acme/1", datetime.now(timezone.utc), "Python")
    repo.save_job(job)
    repo.save_evaluation(FitEvaluation("j1", 80.0, ("python",), (), 0.8))
    status = _score_status(repo)
    assert status["stored_jobs"] == 1
    assert status["scored_jobs"] == 1
    assert status["unscored_jobs"] == 0
    assert status["score_bands"]["75-100"] == 1


def test_catalog_entry_fetch_failure_is_recoverable():
    entry = {"provider": "ashby", "board": "broken"}
    jobs, failure = _fetch_catalog_entry(entry, lambda provider, board: (_ for _ in ()).throw(TimeoutError("offline")))
    assert jobs == []
    assert failure == "TimeoutError"
