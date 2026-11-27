from job_hunt_agent.ai_provider import DeterministicProvider
from job_hunt_agent.orchestrator import plan_source
from job_hunt_agent.cli import main


def test_public_job_page_routes_only_to_bounded_review_steps():
    plan = plan_source("Senior Engineer\nResponsibilities\nApply", DeterministicProvider(), "https://example.com/job")
    assert plan.source_kind == "public_job_page"
    assert plan.steps == ("extract_text", "extract_structured_data", "review")
    assert plan.needs_review is True
    assert "submit" not in plan.steps


def test_blocked_source_hard_stops():
    plan = plan_source("Please login to continue; CAPTCHA required", DeterministicProvider(), "https://example.com")
    assert plan.source_kind == "blocked"
    assert plan.steps == ("stop_and_review",)
    assert plan.needs_review is True


def test_plan_source_cli_is_read_only(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["job-hunt-agent", "plan-source", "login required", "--provider", "deterministic"])
    main()
    output = capsys.readouterr().out
    assert '"stop_and_review"' in output
    assert "submit" not in output

