import json
import threading
from datetime import datetime, timezone
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from job_hunt_agent.review_ui import create_server
from job_hunt_agent.storage import Repository
from job_hunt_agent.schemas import JobRecord


def test_review_ui_serves_local_evidence_api_and_decision(tmp_path):
    repo = Repository(tmp_path / "agent.db")
    repo.initialize()
    server = create_server(repo, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        page = urlopen(base + "/").read().decode()
        assert "Evidence review" in page
        assert "No persisted evidence" in page
        assert "Scored jobs" in page
        assert json.loads(urlopen(base + "/api/evidence?decision=pending").read()) == []
        assert json.loads(urlopen(base + "/api/stats").read())["total"] == 0
        assert json.loads(urlopen(base + "/api/score-status").read())["scored_jobs"] == 0
        assert json.loads(urlopen(base + "/api/application-status").read())["total"] == 0
        assert json.loads(urlopen(base + "/api/integrity-status").read())["total_issues"] == 0
        try:
            urlopen(base + "/api/jobs/submission-handoff?id=missing")
        except HTTPError as error:
            assert error.code == 404
        else:
            raise AssertionError("expected HTTP 404")
        assert json.loads(urlopen(base + "/api/jobs?threshold=80").read()) == []
        try:
            urlopen(base + "/api/jobs/detail?id=missing")
        except HTTPError as error:
            assert error.code == 404
        else:
            raise AssertionError("expected HTTP 404")
        try:
            urlopen(base + "/api/jobs/draft?id=missing")
        except HTTPError as error:
            assert error.code == 404
        else:
            raise AssertionError("expected HTTP 404")
        for path in ("tailored-resume", "interview-prep"):
            try:
                urlopen(base + f"/api/jobs/{path}?id=missing")
            except HTTPError as error:
                assert error.code == 404
            else:
                raise AssertionError("expected HTTP 404")
        try:
            urlopen(base + "/api/jobs/draft-versions?id=missing")
        except HTTPError as error:
            assert error.code == 404
        else:
            raise AssertionError("expected HTTP 404")
        try:
            urlopen(base + "/api/jobs/draft-status?id=missing&type=cover_letter")
        except HTTPError as error:
            assert error.code == 404
        else:
            raise AssertionError("expected HTTP 404")
        try:
            urlopen(base + "/api/evidence/detail?id=missing")
        except HTTPError as error:
            assert error.code == 404
        else:
            raise AssertionError("expected HTTP 404")
        request = Request(base + "/api/evidence/missing/decision", data=json.dumps({"decision": "approved"}).encode(), headers={"Content-Type": "application/json"}, method="POST")
        try:
            urlopen(request)
        except HTTPError as error:
            assert error.code == 400
        else:
            raise AssertionError("expected HTTP 400")
        job_request = Request(base + "/api/jobs/missing/decision", data=json.dumps({"decision": "approved"}).encode(), headers={"Content-Type": "application/json"}, method="POST")
        try:
            urlopen(job_request)
        except HTTPError as error:
            assert error.code == 400
        else:
            raise AssertionError("expected HTTP 400")
    finally:
        server.shutdown()
        server.server_close()


def test_submission_handoff_api_requires_approval(tmp_path):
    repo = Repository(tmp_path / "agent.db")
    repo.initialize()
    repo.save_job(JobRecord("j1", "Engineer", "Example", "test", "https://example.com/jobs/1", datetime.now(timezone.utc), "Python"))
    server = create_server(repo, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}/api/jobs/submission-handoff/j1"
        request = Request(base, data=b'{"platform":"manual-review"}', headers={"Content-Type": "application/json"}, method="POST")
        try:
            urlopen(request)
        except HTTPError as error:
            assert error.code == 400
        else:
            raise AssertionError("unapproved handoff should be rejected")
        repo.decide("j1", "approved")
        result = json.loads(urlopen(request).read())
        assert result["submitted"] is False
        assert result["review_required"] is True
    finally:
        server.shutdown()
        server.server_close()

