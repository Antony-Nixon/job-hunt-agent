"""Small SQLite repository with an append-only audit trail."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .schemas import FitEvaluation, JobRecord, ProfileFact
from .evidence import EvidenceResult
from .retention import RetentionPolicy, expires_at


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Repository:
    def __init__(self, path: str | Path):
        self.connection = sqlite3.connect(path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row

    def initialize(self) -> None:
        self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS profile_facts (key TEXT PRIMARY KEY, value TEXT NOT NULL, source TEXT NOT NULL, verified_at TEXT NOT NULL, confidence REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS jobs (job_id TEXT PRIMARY KEY, title TEXT NOT NULL, company_name TEXT NOT NULL, source_name TEXT NOT NULL, source_url TEXT NOT NULL, retrieved_at TEXT NOT NULL, description TEXT NOT NULL, location TEXT, work_mode TEXT, employment_type TEXT, raw_content_hash TEXT NOT NULL, parser_status TEXT NOT NULL);
            CREATE UNIQUE INDEX IF NOT EXISTS jobs_source_hash ON jobs(source_url, raw_content_hash);
            CREATE TABLE IF NOT EXISTS evaluations (job_id TEXT PRIMARY KEY, score REAL NOT NULL, matched_json TEXT NOT NULL, missing_json TEXT NOT NULL, confidence REAL NOT NULL, rubric_version TEXT NOT NULL, evaluated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS decisions (job_id TEXT PRIMARY KEY, decision TEXT NOT NULL, note TEXT, decided_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS applications (job_id TEXT PRIMARY KEY, status TEXT NOT NULL, note TEXT, updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, occurred_at TEXT NOT NULL, kind TEXT NOT NULL, subject_id TEXT NOT NULL, detail_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS evidence (evidence_id TEXT PRIMARY KEY, url TEXT NOT NULL, final_url TEXT, status TEXT NOT NULL, content_type TEXT, retrieved_bytes INTEGER NOT NULL, text TEXT NOT NULL, classification_json TEXT NOT NULL, extraction_json TEXT, expires_at TEXT, created_at TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS evidence_expiry ON evidence(expires_at);
            CREATE TABLE IF NOT EXISTS evidence_decisions (evidence_id TEXT PRIMARY KEY, decision TEXT NOT NULL, note TEXT NOT NULL, decided_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS draft_decisions (job_id TEXT NOT NULL, draft_type TEXT NOT NULL, decision TEXT NOT NULL, note TEXT NOT NULL, decided_at TEXT NOT NULL, PRIMARY KEY(job_id, draft_type));
            CREATE TABLE IF NOT EXISTS draft_versions (job_id TEXT NOT NULL, draft_type TEXT NOT NULL, content_sha256 TEXT NOT NULL, source_label TEXT NOT NULL, recorded_at TEXT NOT NULL, PRIMARY KEY(job_id, draft_type, content_sha256));
            CREATE TABLE IF NOT EXISTS submission_handoffs (job_id TEXT PRIMARY KEY, platform TEXT NOT NULL, payload_json TEXT NOT NULL, payload_sha256 TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL);
        """)
        evidence_columns = {row[1] for row in self.connection.execute("PRAGMA table_info(evidence)")}
        if "error_category" not in evidence_columns:
            self.connection.execute("ALTER TABLE evidence ADD COLUMN error_category TEXT")
        if "structured_json" not in evidence_columns:
            self.connection.execute("ALTER TABLE evidence ADD COLUMN structured_json TEXT")
        if "provider_name" not in evidence_columns:
            self.connection.execute("ALTER TABLE evidence ADD COLUMN provider_name TEXT")
        if "provider_model" not in evidence_columns:
            self.connection.execute("ALTER TABLE evidence ADD COLUMN provider_model TEXT")
        self.connection.commit()

    def save_evidence(self, evidence: EvidenceResult, policy: RetentionPolicy = RetentionPolicy()) -> str:
        """Persist provenance and review metadata; raw text is explicitly expiring."""
        import hashlib
        evidence_id = hashlib.sha256(f"{evidence.url}|{evidence.final_url or ''}|{evidence.retrieved_bytes}|{evidence.text}".encode()).hexdigest()
        expiry = expires_at("raw_source", datetime.now(timezone.utc), policy)
        extraction = None if evidence.extraction is None else {
            "title": evidence.extraction.title, "company_name": evidence.extraction.company_name,
            "location": evidence.extraction.location, "work_mode": evidence.extraction.work_mode,
            "description": evidence.extraction.description, "links": evidence.extraction.links,
            "uncertainty": evidence.extraction.uncertainty,
        }
        self.connection.execute(
            "INSERT OR REPLACE INTO evidence(evidence_id,url,final_url,status,content_type,retrieved_bytes,text,classification_json,extraction_json,expires_at,created_at,error_category,structured_json,provider_name,provider_model) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (evidence_id, evidence.url, evidence.final_url, evidence.status, evidence.content_type,
             evidence.retrieved_bytes, evidence.text, json.dumps(evidence.classification.__dict__, sort_keys=True),
             json.dumps(extraction, sort_keys=True) if extraction else None, expiry.isoformat() if expiry else None, _now(), evidence.error_category,
             json.dumps(evidence.structured_fields, sort_keys=True) if evidence.structured_fields else None, evidence.provider_name, evidence.provider_model),
        )
        self.connection.commit()
        self.event("evidence_saved", evidence_id, url=evidence.url, status=evidence.status)
        return evidence_id

    def purge_expired_evidence(self, now: datetime | None = None) -> int:
        """Delete only expired raw evidence; audit events remain append-only."""
        current = (now or datetime.now(timezone.utc)).isoformat()
        rows = list(self.connection.execute("SELECT evidence_id FROM evidence WHERE expires_at IS NOT NULL AND expires_at <= ?", (current,)))
        self.connection.execute("DELETE FROM evidence WHERE expires_at IS NOT NULL AND expires_at <= ?", (current,))
        self.connection.commit()
        for row in rows:
            self.event("evidence_expired", row["evidence_id"])
        return len(rows)

    def evidence(self, limit: int = 100) -> list[sqlite3.Row]:
        if limit < 1:
            raise ValueError("limit must be positive")
        return list(self.connection.execute("SELECT evidence_id, url, final_url, status, content_type, retrieved_bytes, classification_json, extraction_json, structured_json, error_category, provider_name, provider_model, expires_at, created_at FROM evidence ORDER BY created_at DESC LIMIT ?", (limit,)))

    def evidence_stats(self) -> dict[str, int]:
        stats = {"total": 0, "ok": 0, "error": 0, "pending": 0, "approved": 0, "rejected": 0, "deferred": 0}
        stats["total"] = self.connection.execute("SELECT COUNT(*) FROM evidence").fetchone()[0]
        for row in self.connection.execute("SELECT status, COUNT(*) AS count FROM evidence GROUP BY status"):
            stats[row["status"]] = row["count"]
        for row in self.connection.execute("SELECT decision, COUNT(*) AS count FROM evidence_decisions GROUP BY decision"):
            stats[row["decision"]] = row["count"]
        stats["pending"] = stats["total"] - sum(stats[key] for key in ("approved", "rejected", "deferred"))
        return stats

    def decide_evidence(self, evidence_id: str, decision: str, note: str = "") -> None:
        if decision not in {"approved", "rejected", "deferred"}:
            raise ValueError("invalid evidence decision")
        exists = self.connection.execute("SELECT 1 FROM evidence WHERE evidence_id = ?", (evidence_id,)).fetchone()
        if not exists:
            raise ValueError("unknown evidence_id")
        self.connection.execute("INSERT OR REPLACE INTO evidence_decisions VALUES(?,?,?,?)", (evidence_id, decision, note, _now()))
        self.connection.commit()
        self.event("evidence_review_decision", evidence_id, decision=decision)

    def promote_approved_evidence(self, evidence_id: str, job_id: str, title: str, company_name: str, source_name: str) -> bool:
        """Create a canonical job only from evidence explicitly approved by a human."""
        evidence = self.connection.execute("SELECT * FROM evidence WHERE evidence_id = ?", (evidence_id,)).fetchone()
        decision = self.connection.execute("SELECT decision FROM evidence_decisions WHERE evidence_id = ?", (evidence_id,)).fetchone()
        if not evidence or not decision:
            raise ValueError("evidence must exist and be reviewed before promotion")
        if decision["decision"] != "approved":
            raise ValueError("only approved evidence can be promoted")
        job = JobRecord(job_id, title, company_name, source_name, evidence["final_url"] or evidence["url"], datetime.fromisoformat(evidence["created_at"]), evidence["text"], parser_status="parsed")
        added = self.save_job(job)
        self.event("evidence_promoted", evidence_id, job_id=job_id, added=added)
        return added

    def decide_draft(self, job_id: str, draft_type: str, decision: str, note: str = "") -> None:
        if draft_type not in {"cover_letter", "tailored_resume", "interview_prep"}:
            raise ValueError("invalid draft type")
        if decision not in {"approved", "rejected", "deferred"}:
            raise ValueError("invalid draft decision")
        if not self.connection.execute("SELECT 1 FROM jobs WHERE job_id = ?", (job_id,)).fetchone():
            raise ValueError("unknown job_id")
        self.connection.execute("INSERT OR REPLACE INTO draft_decisions VALUES(?,?,?,?,?)", (job_id, draft_type, decision, note, _now()))
        self.connection.commit()
        self.event("draft_review_decision", job_id, draft_type=draft_type, decision=decision)

    def record_draft_version(self, job_id: str, draft_type: str, content_sha256: str, source_label: str = "local-review") -> None:
        if draft_type not in {"cover_letter", "tailored_resume", "interview_prep"}:
            raise ValueError("invalid draft type")
        if len(content_sha256) != 64 or any(char not in "0123456789abcdef" for char in content_sha256.lower()):
            raise ValueError("content_sha256 must be a SHA-256 hex digest")
        if not self.connection.execute("SELECT 1 FROM jobs WHERE job_id = ?", (job_id,)).fetchone():
            raise ValueError("unknown job_id")
        self.connection.execute("INSERT OR IGNORE INTO draft_versions VALUES(?,?,?,?,?)", (job_id, draft_type, content_sha256.lower(), source_label, _now()))
        self.connection.commit()
        self.event("draft_version_recorded", job_id, draft_type=draft_type, content_sha256=content_sha256.lower())

    def draft_versions(self, job_id: str) -> list[sqlite3.Row]:
        if not self.connection.execute("SELECT 1 FROM jobs WHERE job_id = ?", (job_id,)).fetchone():
            raise ValueError("unknown job_id")
        return list(self.connection.execute("SELECT draft_type, content_sha256, source_label, recorded_at FROM draft_versions WHERE job_id = ? ORDER BY recorded_at DESC", (job_id,)))

    def event(self, kind: str, subject_id: str, **detail: object) -> None:
        self.connection.execute("INSERT INTO events VALUES(NULL,?,?,?,?)", (_now(), kind, subject_id, json.dumps(detail, sort_keys=True)))
        self.connection.commit()

    def save_fact(self, fact: ProfileFact) -> None:
        fact.validate()
        self.connection.execute("INSERT OR REPLACE INTO profile_facts VALUES(?,?,?,?,?)", (fact.key, fact.value, fact.source, fact.verified_at.isoformat(), fact.confidence))
        self.connection.commit(); self.event("profile_fact_saved", fact.key, source=fact.source)

    def facts(self) -> list[ProfileFact]:
        return [ProfileFact(r["key"], r["value"], r["source"], datetime.fromisoformat(r["verified_at"]), r["confidence"]) for r in self.connection.execute("SELECT * FROM profile_facts ORDER BY key")]

    def save_job(self, job: JobRecord) -> bool:
        job.validate()
        try:
            self.connection.execute("INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (job.job_id, job.title, job.company_name, job.source_name, job.source_url, job.retrieved_at.isoformat(), job.description, job.location, job.work_mode, job.employment_type, job.content_hash, job.parser_status))
        except sqlite3.IntegrityError:
            return False
        self.connection.commit(); self.event("job_ingested", job.job_id, source=job.source_name); return True

    def jobs(self) -> list[JobRecord]:
        rows = self.connection.execute("SELECT * FROM jobs ORDER BY retrieved_at DESC")
        return [JobRecord(r["job_id"], r["title"], r["company_name"], r["source_name"], r["source_url"], datetime.fromisoformat(r["retrieved_at"]), r["description"], r["location"], r["work_mode"], r["employment_type"], r["raw_content_hash"], r["parser_status"]) for r in rows]

    def save_evaluation(self, evaluation: FitEvaluation) -> None:
        evaluation.validate()
        self.connection.execute("INSERT OR REPLACE INTO evaluations VALUES(?,?,?,?,?,?,?)", (evaluation.job_id, evaluation.score, json.dumps(evaluation.matched_requirements), json.dumps(evaluation.missing_requirements), evaluation.confidence, evaluation.rubric_version, _now()))
        self.connection.commit(); self.event("job_scored", evaluation.job_id, score=evaluation.score)

    def queue(self, threshold: float) -> list[sqlite3.Row]:
        return list(self.connection.execute("SELECT j.*, e.score, e.matched_json, e.missing_json, e.confidence FROM jobs j JOIN evaluations e USING(job_id) LEFT JOIN decisions d USING(job_id) WHERE e.score >= ? AND d.job_id IS NULL ORDER BY e.score DESC", (threshold,)))

    def decide(self, job_id: str, decision: str, note: str = "") -> None:
        if decision not in {"approved", "rejected", "deferred"}: raise ValueError("invalid decision")
        if not self.connection.execute("SELECT 1 FROM jobs WHERE job_id = ?", (job_id,)).fetchone():
            raise ValueError("unknown job_id")
        self.connection.execute("INSERT OR REPLACE INTO decisions VALUES(?,?,?,?)", (job_id, decision, note, _now()))
        self.connection.commit(); self.event("review_decision", job_id, decision=decision)

    def application(self, job_id: str, status: str, note: str = "") -> None:
        allowed = {"draft_ready", "review_required", "approved", "submitted", "interview", "rejected", "withdrawn"}
        if status not in allowed: raise ValueError("invalid application status")
        if not self.connection.execute("SELECT 1 FROM jobs WHERE job_id = ?", (job_id,)).fetchone():
            raise ValueError("unknown job_id")
        if status == "submitted":
            decision = self.connection.execute("SELECT decision FROM decisions WHERE job_id = ?", (job_id,)).fetchone()
            if not decision or decision["decision"] != "approved":
                raise ValueError("submitted status requires an approved job decision")
        self.connection.execute("INSERT OR REPLACE INTO applications VALUES(?,?,?,?)", (job_id, status, note, _now()))
        self.connection.commit(); self.event("application_status", job_id, status=status)

    def application_stats(self) -> dict[str, int]:
        """Return lifecycle counts without exposing application notes or content."""
        stats: dict[str, int] = {status: 0 for status in ("draft_ready", "review_required", "approved", "submitted", "interview", "rejected", "withdrawn")}
        for row in self.connection.execute("SELECT status, COUNT(*) AS count FROM applications GROUP BY status"):
            stats[row["status"]] = row["count"]
        stats["total"] = sum(stats.values())
        return stats

    def integrity_report(self) -> dict[str, int]:
        """Count referential-integrity issues without repairing or deleting anything."""
        checks = {
            "orphan_evaluations": "SELECT COUNT(*) FROM evaluations e LEFT JOIN jobs j ON j.job_id=e.job_id WHERE j.job_id IS NULL",
            "orphan_decisions": "SELECT COUNT(*) FROM decisions d LEFT JOIN jobs j ON j.job_id=d.job_id WHERE j.job_id IS NULL",
            "orphan_applications": "SELECT COUNT(*) FROM applications a LEFT JOIN jobs j ON j.job_id=a.job_id WHERE j.job_id IS NULL",
            "orphan_draft_decisions": "SELECT COUNT(*) FROM draft_decisions d LEFT JOIN jobs j ON j.job_id=d.job_id WHERE j.job_id IS NULL",
            "orphan_draft_versions": "SELECT COUNT(*) FROM draft_versions d LEFT JOIN jobs j ON j.job_id=d.job_id WHERE j.job_id IS NULL",
        }
        result = {name: self.connection.execute(query).fetchone()[0] for name, query in checks.items()}
        result["total_issues"] = sum(result.values())
        return result

    def save_submission_handoff(self, job_id: str, platform: str, payload: dict, payload_sha256: str) -> None:
        if not self.connection.execute("SELECT 1 FROM jobs WHERE job_id = ?", (job_id,)).fetchone():
            raise ValueError("unknown job_id")
        decision = self.connection.execute("SELECT decision FROM decisions WHERE job_id = ?", (job_id,)).fetchone()
        if not decision or decision["decision"] != "approved":
            raise ValueError("submission handoff requires an approved job decision")
        self.connection.execute("INSERT OR REPLACE INTO submission_handoffs VALUES(?,?,?,?,?,?)", (job_id, platform, json.dumps(payload, sort_keys=True), payload_sha256, "prepared", _now()))
        self.connection.commit()
        self.event("submission_handoff_prepared", job_id, platform=platform, payload_sha256=payload_sha256)

    def submission_handoff(self, job_id: str) -> sqlite3.Row | None:
        return self.connection.execute("SELECT job_id, platform, payload_json, payload_sha256, status, created_at FROM submission_handoffs WHERE job_id = ?", (job_id,)).fetchone()
