from datetime import datetime, timezone

from job_hunt_agent.drafting import cover_letter_draft
from job_hunt_agent.scoring import evaluate
from job_hunt_agent.schemas import JobRecord, ProfileFact
from job_hunt_agent.storage import Repository


def job() -> JobRecord:
    return JobRecord("j1", "Automation Engineer", "Example Co", "fixture", "https://example.com/jobs/1", datetime.now(timezone.utc), "Python SQL API automation work")


def facts() -> list[ProfileFact]:
    return [ProfileFact("skills", "Python SQL API automation", "resume.pdf", datetime.now(timezone.utc))]


def test_score_explains_matches_and_missing_requirements():
    result = evaluate(job(), facts(), ("Automation Engineer",))
    assert result.score == 100
    assert "python" in result.matched_requirements
    assert result.missing_requirements == ()


def test_score_does_not_treat_generic_shared_words_as_skill_matches():
    unrelated = JobRecord("j2", "VP Finance", "Example Co", "fixture", "https://example.com/jobs/2", datetime.now(timezone.utc), "Own finance, forecasting, accounting, and investments.")
    assert evaluate(unrelated, facts(), ("Automation Engineer",)).score == 0


def test_draft_uses_only_verified_facts():
    draft = cover_letter_draft(job(), facts(), "Avery")
    assert "Python SQL API automation" in draft
    assert "REVIEW REQUIRED" in draft


def test_repository_deduplicates_and_audits(tmp_path):
    repository = Repository(tmp_path / "agent.db")
    repository.initialize()
    assert repository.save_job(job()) is True
    assert repository.save_job(job()) is False
    repository.save_fact(facts()[0])
    repository.save_evaluation(evaluate(job(), facts(), ("Automation Engineer",)))
    assert len(repository.queue(80)) == 1
    repository.decide("j1", "approved")
    assert repository.queue(80) == []

