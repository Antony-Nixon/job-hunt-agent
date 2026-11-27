"""Minimal localhost review interface for persisted evidence."""

from __future__ import annotations

import html
import hashlib
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .storage import Repository
from .drafting import cover_letter_draft
from .resume import MasterResume, interview_prep_markdown, tailored_resume_markdown
from .submission import prepare_handoff


def _rows(repository: Repository, status: str | None = None, decision: str | None = None) -> list[dict[str, object]]:
    rows = repository.evidence(200)
    decisions = {row["evidence_id"]: row["decision"] for row in repository.connection.execute("SELECT evidence_id, decision FROM evidence_decisions")}
    result = [{"evidence_id": row["evidence_id"], "url": row["url"], "status": row["status"], "expires_at": row["expires_at"], "decision": decisions.get(row["evidence_id"])} for row in rows]
    return [item for item in result if (not status or item["status"] == status) and (not decision or item["decision"] == decision)]


def _job_rows(repository: Repository, threshold: float = 0.0) -> list[dict[str, object]]:
    return [{"job_id": row["job_id"], "title": row["title"], "company_name": row["company_name"], "score": row["score"], "confidence": row["confidence"], "source_url": row["source_url"]} for row in repository.queue(threshold)]


def _score_status(repository: Repository) -> dict[str, object]:
    rows = list(repository.connection.execute("SELECT score, decision FROM evaluations e LEFT JOIN decisions d USING(job_id)"))
    bands = {"0-24.9": 0, "25-49.9": 0, "50-74.9": 0, "75-100": 0}
    for row in rows:
        score = float(row["score"])
        key = "0-24.9" if score < 25 else "25-49.9" if score < 50 else "50-74.9" if score < 75 else "75-100"
        bands[key] += 1
    return {"stored_jobs": repository.connection.execute("SELECT COUNT(*) FROM jobs").fetchone()[0], "scored_jobs": len(rows), "reviewed_scored_jobs": sum(row["decision"] is not None for row in rows), "score_bands": bands}


def _page(repository: Repository) -> bytes:
    items = _rows(repository)
    jobs = _job_rows(repository, 0.0)
    body = "".join(
        f"<li><code>{html.escape(str(item['evidence_id']))}</code> — {html.escape(str(item['status']))} — "
        f"<a href=\"{html.escape(str(item['url']))}\">source</a> — decision: {html.escape(str(item['decision'] or 'pending'))} "
        f"<button onclick=\"decide('{html.escape(str(item['evidence_id']))}','approved')\">Approve</button> "
        f"<button onclick=\"decide('{html.escape(str(item['evidence_id']))}','rejected')\">Reject</button> "
        f"<button onclick=\"decide('{html.escape(str(item['evidence_id']))}','deferred')\">Defer</button> "
        f"<details><summary>Promote</summary><input id=\"job-{html.escape(str(item['evidence_id']))}\" placeholder=\"job id\"><input id=\"title-{html.escape(str(item['evidence_id']))}\" placeholder=\"title\"><input id=\"company-{html.escape(str(item['evidence_id']))}\" placeholder=\"company\"><button onclick=\"promote('{html.escape(str(item['evidence_id']))}')\">Create canonical job</button></details></li>"
        for item in items
    )
    job_body = "".join(f"<li><code>{html.escape(str(job['job_id']))}</code> — {html.escape(str(job['title']))} — {html.escape(str(job['company_name']))} — score {job['score']:.1f} "
                        f"<a href=\"/api/jobs/detail?id={html.escape(str(job['job_id']))}\">details</a> "
                        f"<a href=\"/api/jobs/draft?id={html.escape(str(job['job_id']))}\">cover-letter</a> "
                        f"<a href=\"/api/jobs/tailored-resume?id={html.escape(str(job['job_id']))}\">resume</a> "
                        f"<a href=\"/api/jobs/interview-prep?id={html.escape(str(job['job_id']))}\">prep</a> "
                        f"<a href=\"/api/jobs/draft-versions?id={html.escape(str(job['job_id']))}\">versions</a> "
                        f"<a href=\"/api/jobs/draft-status?id={html.escape(str(job['job_id']))}&type=cover_letter\">compare cover-letter</a> "
                        f"<a href=\"/api/jobs/draft-status?id={html.escape(str(job['job_id']))}&type=tailored_resume\">compare resume</a> "
                        f"<a href=\"/api/jobs/draft-status?id={html.escape(str(job['job_id']))}&type=interview_prep\">compare prep</a> "
                        f"<button onclick=\"jobDecision('{html.escape(str(job['job_id']))}','approved')\">Approve</button> "
                        f"<button onclick=\"jobDecision('{html.escape(str(job['job_id']))}','rejected')\">Reject</button> "
                        f"<button onclick=\"jobDecision('{html.escape(str(job['job_id']))}','deferred')\">Defer</button></li>" for job in jobs)
    return ("<!doctype html><meta charset='utf-8'><title>Job Hunt Agent Review</title>"
            "<h1>Evidence review</h1><p>Local review only. No application submission is available here.</p>"
            f"<p id='score-status'>Score calibration: {html.escape(json.dumps(_score_status(repository), sort_keys=True))}</p>"
            f"<ul>{body or '<li>No persisted evidence.</li>'}</ul><h2>Scored jobs</h2><ul>{job_body or '<li>No scored jobs pending review.</li>'}</ul>"
            "<script>async function decide(id,decision){await fetch('/api/evidence/'+id+'/decision',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({decision})});location.reload()}"
            "async function promote(id){let v=x=>document.getElementById(x+'-'+id).value;let r=await fetch('/api/evidence/'+id+'/promote',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({job_id:v('job'),title:v('title'),company_name:v('company')})});if(!r.ok)alert(await r.text());else location.reload()}"
            "async function jobDecision(id,decision){let r=await fetch('/api/jobs/'+id+'/decision',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({decision})});if(!r.ok)alert(await r.text());else location.reload()}</script>").encode()


def create_server(repository: Repository, host: str = "127.0.0.1", port: int = 8765, master_resume: Path | None = None) -> ThreadingHTTPServer:
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("review UI must bind to localhost")

    class Handler(BaseHTTPRequestHandler):
        def _send(self, status: int, payload: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            if parsed.path == "/api/evidence":
                self._send(200, json.dumps(_rows(repository, query.get("status", [None])[0], query.get("decision", [None])[0])).encode(), "application/json")
            elif parsed.path == "/api/stats":
                self._send(200, json.dumps(repository.evidence_stats()).encode(), "application/json")
            elif parsed.path == "/api/score-status":
                self._send(200, json.dumps(_score_status(repository)).encode(), "application/json")
            elif parsed.path == "/api/application-status":
                self._send(200, json.dumps(repository.application_stats()).encode(), "application/json")
            elif parsed.path == "/api/integrity-status":
                self._send(200, json.dumps(repository.integrity_report()).encode(), "application/json")
            elif parsed.path == "/api/jobs":
                try:
                    threshold = float(query.get("threshold", [0])[0])
                    self._send(200, json.dumps(_job_rows(repository, threshold)).encode(), "application/json")
                except ValueError:
                    self._send(400, b'{"error":"invalid threshold"}', "application/json")
            elif parsed.path == "/api/jobs/detail":
                job_id = query.get("id", [None])[0]
                row = repository.connection.execute("SELECT j.job_id, j.title, j.company_name, j.source_name, j.source_url, j.retrieved_at, j.description, j.location, j.work_mode, j.employment_type, j.parser_status, e.score, e.matched_json, e.missing_json, e.confidence, e.rubric_version, d.decision, d.note AS decision_note FROM jobs j LEFT JOIN evaluations e USING(job_id) LEFT JOIN decisions d USING(job_id) WHERE j.job_id = ?", (job_id,)).fetchone()
                self._send(200 if row else 404, json.dumps(dict(row) if row else {"error": "not found"}).encode(), "application/json")
            elif parsed.path == "/api/jobs/submission-handoff":
                job_id = query.get("id", [None])[0]
                row = repository.submission_handoff(job_id)
                self._send(200 if row else 404, json.dumps(dict(row) if row else {"error": "not found"}).encode(), "application/json")
            elif parsed.path == "/api/jobs/draft":
                job_id = query.get("id", [None])[0]
                job = next((item for item in repository.jobs() if item.job_id == job_id), None)
                if not job:
                    self._send(404, b'{"error":"not found"}', "application/json")
                else:
                    markdown = cover_letter_draft(job, repository.facts(), "Candidate")
                    self._send(200, json.dumps({"job_id": job_id, "type": "cover_letter", "review_required": True, "content_sha256": hashlib.sha256(markdown.encode()).hexdigest(), "markdown": markdown}).encode(), "application/json")
            elif parsed.path == "/api/jobs/draft-versions":
                job_id = query.get("id", [None])[0]
                try:
                    self._send(200, json.dumps([dict(row) for row in repository.draft_versions(job_id)]).encode(), "application/json")
                except ValueError:
                    self._send(404, b'{"error":"not found"}', "application/json")
            elif parsed.path == "/api/jobs/draft-status":
                job_id = query.get("id", [None])[0]
                draft_type = query.get("type", ["cover_letter"])[0]
                job = next((item for item in repository.jobs() if item.job_id == job_id), None)
                if not job:
                    self._send(404, b'{"error":"not found"}', "application/json")
                elif draft_type in {"cover_letter", "tailored_resume", "interview_prep"} and (draft_type == "cover_letter" or master_resume):
                    if draft_type == "cover_letter":
                        markdown = cover_letter_draft(job, repository.facts(), "Candidate")
                    else:
                        resume = MasterResume.load(master_resume)
                        markdown = tailored_resume_markdown(resume, job) if draft_type == "tailored_resume" else interview_prep_markdown(resume, job)
                    current_hash = hashlib.sha256(markdown.encode()).hexdigest()
                    versions = [dict(row) for row in repository.draft_versions(job_id)]
                    hashes = [row["content_sha256"] for row in versions if row["draft_type"] == draft_type]
                    self._send(200, json.dumps({"job_id": job_id, "draft_type": draft_type, "current_sha256": current_hash, "state": "unchanged" if current_hash in hashes else "new_or_changed", "versions": versions}).encode(), "application/json")
                else:
                    self._send(400, b'{"error":"draft-status requires --master-resume for this draft type"}', "application/json")
            elif parsed.path in {"/api/jobs/tailored-resume", "/api/jobs/interview-prep"}:
                job_id = query.get("id", [None])[0]
                job = next((item for item in repository.jobs() if item.job_id == job_id), None)
                if not job:
                    self._send(404, b'{"error":"not found"}', "application/json")
                elif not master_resume:
                    self._send(400, b'{"error":"review server was not configured with --master-resume"}', "application/json")
                else:
                    resume = MasterResume.load(master_resume)
                    kind = "tailored_resume" if parsed.path.endswith("tailored-resume") else "interview_prep"
                    markdown = tailored_resume_markdown(resume, job) if kind == "tailored_resume" else interview_prep_markdown(resume, job)
                    self._send(200, json.dumps({"job_id": job_id, "type": kind, "review_required": True, "content_sha256": hashlib.sha256(markdown.encode()).hexdigest(), "markdown": markdown}).encode(), "application/json")
            elif parsed.path == "/api/evidence/detail":
                evidence_id = query.get("id", [None])[0]
                row = repository.connection.execute("SELECT evidence_id, url, final_url, status, content_type, retrieved_bytes, text, classification_json, extraction_json, structured_json, error_category, provider_name, provider_model, expires_at, created_at FROM evidence WHERE evidence_id = ?", (evidence_id,)).fetchone()
                self._send(200 if row else 404, json.dumps(dict(row) if row else {"error": "not found"}).encode(), "application/json")
            elif parsed.path == "/":
                self._send(200, _page(repository), "text/html; charset=utf-8")
            else:
                self._send(404, b"not found", "text/plain")

        def do_POST(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            prefix = "/api/evidence/"
            if not path.startswith(prefix) or not (path.endswith("/decision") or path.endswith("/promote")):
                job_prefix = "/api/jobs/"
                if path.startswith(job_prefix) and path.endswith("/decision"):
                    try:
                        length = min(int(self.headers.get("Content-Length", "0")), 16_384)
                        payload = json.loads(self.rfile.read(length))
                        repository.decide(path[len(job_prefix):-len("/decision")], str(payload["decision"]), str(payload.get("note", "")))
                        self._send(200, b'{"ok":true}', "application/json")
                    except (ValueError, KeyError, json.JSONDecodeError) as exc:
                        self._send(400, json.dumps({"error": str(exc)}).encode(), "application/json")
                    return
                handoff_prefix = "/api/jobs/submission-handoff/"
                if path.startswith(handoff_prefix):
                    try:
                        length = min(int(self.headers.get("Content-Length", "0")), 16_384)
                        payload = json.loads(self.rfile.read(length))
                        job_id = path[len(handoff_prefix):]
                        job = next((item for item in repository.jobs() if item.job_id == job_id), None)
                        if not job:
                            raise ValueError("unknown job_id")
                        handoff = prepare_handoff(job, str(payload.get("platform", "manual-review")))
                        repository.save_submission_handoff(handoff.job_id, handoff.platform, handoff.payload, handoff.payload_sha256)
                        self._send(200, json.dumps({"job_id": handoff.job_id, "platform": handoff.platform, "payload_sha256": handoff.payload_sha256, "review_required": True, "submitted": False}).encode(), "application/json")
                    except (ValueError, KeyError, json.JSONDecodeError) as exc:
                        self._send(400, json.dumps({"error": str(exc)}).encode(), "application/json")
                    return
                draft_prefix = "/api/jobs/draft-decision/"
                if path.startswith(draft_prefix):
                    try:
                        length = min(int(self.headers.get("Content-Length", "0")), 16_384)
                        payload = json.loads(self.rfile.read(length))
                        repository.decide_draft(path[len(draft_prefix):], str(payload["draft_type"]), str(payload["decision"]), str(payload.get("note", "")))
                        self._send(200, b'{"ok":true}', "application/json")
                    except (ValueError, KeyError, json.JSONDecodeError) as exc:
                        self._send(400, json.dumps({"error": str(exc)}).encode(), "application/json")
                    return
                self._send(404, b"not found", "text/plain")
                return
            try:
                length = min(int(self.headers.get("Content-Length", "0")), 16_384)
                payload = json.loads(self.rfile.read(length))
                evidence_id = path[len(prefix):]
                if path.endswith("/decision"):
                    repository.decide_evidence(evidence_id[:-len("/decision")], str(payload["decision"]), str(payload.get("note", "")))
                else:
                    evidence_id = evidence_id[:-len("/promote")]
                    repository.promote_approved_evidence(evidence_id, str(payload["job_id"]), str(payload["title"]), str(payload["company_name"]), "reviewed-public-evidence")
                self._send(200, b'{"ok":true}', "application/json")
            except (ValueError, KeyError, json.JSONDecodeError) as exc:
                self._send(400, json.dumps({"error": str(exc)}).encode(), "application/json")

        def log_message(self, format: str, *args: object) -> None:
            return

    return ThreadingHTTPServer((host, port), Handler)
