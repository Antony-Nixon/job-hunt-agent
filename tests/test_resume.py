import json
from datetime import datetime, timezone

from job_hunt_agent.resume import MasterResume, interview_prep_markdown, tailored_resume_markdown
from job_hunt_agent.schemas import JobRecord


def master_resume(tmp_path):
    content = {"identity": {"name": "Avery Example"}, "contact": {"email": "avery@example.com"}, "summary": "Automation engineer.", "experience": [{"id": "experience.example", "role": "Engineer", "organization": "Example Co", "period": "2025", "highlights": ["Built Python API automation with idempotent retries."]}], "projects": [], "skills": ["Python", "API", "Automation"], "education": "BSc Example"}
    path = tmp_path / "resume.json"
    path.write_text(json.dumps(content), encoding="utf-8")
    return MasterResume.load(path)


def job():
    return JobRecord("job-1", "Automation Engineer", "Example Co", "fixture", "https://example.com/jobs/1", datetime.now(timezone.utc), "Build Python API automation with safe retries.")


def test_master_resume_becomes_traceable_facts(tmp_path):
    keys = {fact.key for fact in master_resume(tmp_path).facts()}
    assert {"identity.name", "skills", "experience.example.evidence"} <= keys


def test_tailored_resume_only_uses_source_content(tmp_path):
    output = tailored_resume_markdown(master_resume(tmp_path), job())
    assert "Built Python API automation with idempotent retries." in output
    assert "Every claim above is selected" in output


def test_interview_prep_has_role_specific_review_material(tmp_path):
    output = interview_prep_markdown(master_resume(tmp_path), job())
    assert "Interview Prep: Automation Engineer" in output
    assert "STAR Stories to Prepare" in output

