"""Local-only command line for the safe MVP."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .drafting import cover_letter_draft
from .schemas import JobRecord, ProfileFact
from .scoring import evaluate
from .resume import MasterResume, interview_prep_markdown, tailored_resume_markdown
from .sources import PUBLIC_PROVIDERS, fetch_public_board
from .storage import Repository
from .profiles import ProfilePaths
from . import gmail_local
from .gmail_reader import scan_alerts
from .ai_provider import DeterministicProvider, GeminiProvider, OllamaProvider, select_provider
from .evidence import inspect_public_link
from .review_ui import create_server
from .submission import prepare_handoff
from .orchestrator import plan_source


def _repo(path: str) -> Repository:
    repository = Repository(path)
    repository.initialize()
    return repository


def _catalog_status(entries: list[dict], repository: Repository) -> dict:
    """Report catalog coverage using stored jobs and explicit review decisions."""
    jobs = repository.jobs()
    decisions = {row["job_id"]: row["decision"] for row in repository.connection.execute("SELECT job_id, decision FROM decisions")}
    results = []
    for entry in entries:
        provider, board = entry.get("provider"), entry.get("board")
        host = {"ashby": "jobs.ashbyhq.com", "greenhouse": "boards.greenhouse.io", "lever": "jobs.lever.co"}.get(provider, "")
        marker = f"{host}/{board.lower()}"
        matching = [job for job in jobs if marker in job.source_url.lower()]
        results.append({"name": entry.get("name", board), "provider": provider, "board": board, "enabled": entry.get("enabled", True),
                        "stored_jobs": len(matching), "reviewed_jobs": sum(1 for job in matching if job.job_id in decisions),
                        "decisions": {decision: sum(1 for job in matching if decisions.get(job.job_id) == decision) for decision in ("approved", "rejected", "deferred")}})
    return {"catalog_entries": len(entries), "enabled_entries": sum(1 for entry in entries if entry.get("enabled", True)), "boards": results}


def _load_catalog(catalog: Path) -> list[dict]:
    if not catalog.exists():
        raise SystemExit(f"Board catalog not found: {catalog}")
    try:
        entries = json.loads(catalog.read_text(encoding="utf-8"))
        if not isinstance(entries, list) or any(not isinstance(entry, dict) or entry.get("provider") not in PUBLIC_PROVIDERS or not entry.get("board") for entry in entries):
            raise ValueError("catalog entries must define provider, board, and optional enabled/name")
        return entries
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise SystemExit(f"Invalid board catalog: {exc}") from exc


def _score_status(repository: Repository) -> dict:
    rows = list(repository.connection.execute("SELECT e.score, e.confidence, d.decision FROM evaluations e LEFT JOIN decisions d USING(job_id)"))
    bands = {"0-24.9": 0, "25-49.9": 0, "50-74.9": 0, "75-100": 0}
    for row in rows:
        score = float(row["score"])
        key = "0-24.9" if score < 25 else "25-49.9" if score < 50 else "50-74.9" if score < 75 else "75-100"
        bands[key] += 1
    return {"stored_jobs": repository.connection.execute("SELECT COUNT(*) FROM jobs").fetchone()[0], "scored_jobs": len(rows),
            "unscored_jobs": repository.connection.execute("SELECT COUNT(*) FROM jobs WHERE job_id NOT IN (SELECT job_id FROM evaluations)").fetchone()[0],
            "score_bands": bands, "reviewed_scored_jobs": sum(1 for row in rows if row["decision"] is not None)}


def _fetch_catalog_entry(entry: dict, fetcher=fetch_public_board) -> tuple[list[JobRecord], str | None]:
    """Fetch one permitted catalog entry; return a safe recovery label on transient failure."""
    try:
        return fetcher(entry["provider"], entry["board"]), None
    except (OSError, TimeoutError) as exc:
        return [], type(exc).__name__


def main() -> None:
    parser = argparse.ArgumentParser(description="Local, review-first Job Hunt Agent")
    parser.add_argument("--database", type=Path)
    parser.add_argument("--profile", help="local profile id; uses private/profiles/PROFILE_ID")
    parser.add_argument("--private-root", type=Path, default=Path("private/profiles"))
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init")
    profile_init = commands.add_parser("profile-init")
    profile_init.add_argument("profile_id")
    profile_init.add_argument("--master-resume", type=Path, required=True)
    gmail_authorize = commands.add_parser("gmail-authorize")
    gmail_authorize.add_argument("--credentials", type=Path, required=True)
    commands.add_parser("gmail-status")
    commands.add_parser("gmail-disconnect")
    ai_status = commands.add_parser("ai-status")
    ai_status.add_argument("--model", default="llama3.2")
    ai_status.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    ai_status.add_argument("--provider", choices=["auto", "ollama", "gemini", "deterministic"], default="auto")
    ai_status.add_argument("--gemini-model", default="gemini-2.5-flash")
    plan = commands.add_parser("plan-source", help="show the bounded, read-only workflow for source text")
    plan.add_argument("text")
    plan.add_argument("--url")
    plan.add_argument("--provider", choices=["deterministic"], default="deterministic")
    inspect = commands.add_parser("inspect-link")
    inspect.add_argument("url")
    inspect.add_argument("--provider", choices=["auto", "gemini", "deterministic"], default="auto")
    inspect.add_argument("--gemini-model", default="gemini-2.5-flash")
    inspect.add_argument("--save", action="store_true", help="persist evidence in the selected database")
    inspect.add_argument("--database", type=Path)
    evidence_list = commands.add_parser("evidence-list")
    evidence_list.add_argument("--database", type=Path, required=True)
    evidence_list.add_argument("--limit", type=int, default=50)
    evidence_list.add_argument("--json", action="store_true", help="emit review metadata as JSON")
    evidence_purge = commands.add_parser("evidence-purge")
    evidence_purge.add_argument("--database", type=Path, required=True)
    evidence_stats = commands.add_parser("evidence-stats")
    evidence_stats.add_argument("--database", type=Path, required=True)
    evidence_decide = commands.add_parser("evidence-decide")
    evidence_decide.add_argument("evidence_id")
    evidence_decide.add_argument("decision", choices=["approved", "rejected", "deferred"])
    evidence_decide.add_argument("--note", default="")
    evidence_decide.add_argument("--database", type=Path, required=True)
    evidence_promote = commands.add_parser("evidence-promote")
    evidence_promote.add_argument("evidence_id")
    evidence_promote.add_argument("job_id")
    evidence_promote.add_argument("title")
    evidence_promote.add_argument("company_name")
    evidence_promote.add_argument("--source-name", default="reviewed-public-evidence")
    evidence_promote.add_argument("--database", type=Path, required=True)
    evidence_promote.add_argument("--score", action="store_true", help="score the newly promoted job deterministically")
    evidence_promote.add_argument("--roles", nargs="*", default=[])
    review_server = commands.add_parser("review-server")
    review_server.add_argument("--database", type=Path, required=True)
    review_server.add_argument("--host", default="127.0.0.1")
    review_server.add_argument("--port", type=int, default=8765)
    review_server.add_argument("--master-resume", type=Path)
    draft_record = commands.add_parser("draft-record")
    draft_record.add_argument("job_id"); draft_record.add_argument("draft_type", choices=["cover_letter", "tailored_resume", "interview_prep"]); draft_record.add_argument("content_sha256"); draft_record.add_argument("--source-label", default="local-review"); draft_record.add_argument("--database", type=Path, required=True)
    gmail_scan = commands.add_parser("gmail-scan-alerts")
    gmail_scan.add_argument("--query", default="newer_than:30d (job OR jobs OR hiring OR career OR careers OR vacancy OR opportunity OR role)")
    gmail_scan.add_argument("--max-messages", type=int, default=50)
    fact = commands.add_parser("add-fact")
    fact.add_argument("key"); fact.add_argument("value"); fact.add_argument("--source", required=True)
    fact.add_argument("--confidence", type=float, default=1)
    master = commands.add_parser("import-master-resume")
    master.add_argument("file", type=Path)
    importer = commands.add_parser("import-jobs")
    importer.add_argument("file", type=Path); importer.add_argument("--source", required=True)
    board = commands.add_parser("ingest-public-board")
    board.add_argument("provider", choices=sorted(PUBLIC_PROVIDERS)); board.add_argument("board")
    board_scan = commands.add_parser("scan-public-boards")
    board_scan.add_argument("--catalog", type=Path)
    catalog_status = commands.add_parser("catalog-status", help="report stored/reviewed coverage of a public-board catalog")
    catalog_status.add_argument("--catalog", type=Path)
    commands.add_parser("score-status", help="report score coverage and review calibration state")
    commands.add_parser("application-status", help="report application lifecycle counts")
    commands.add_parser("integrity-status", help="report canonical-table integrity issues")
    submission_prepare = commands.add_parser("submission-prepare", help="prepare an approval-gated handoff; never submits")
    submission_prepare.add_argument("job_id")
    submission_prepare.add_argument("--platform", default="manual-review")
    submission_prepare.add_argument("--database", type=Path, required=True)
    scorer = commands.add_parser("score"); scorer.add_argument("--roles", nargs="*", default=[])
    queue = commands.add_parser("queue"); queue.add_argument("--threshold", type=float, default=80)
    decision = commands.add_parser("decide")
    decision.add_argument("job_id"); decision.add_argument("decision", choices=["approved", "rejected", "deferred"])
    decision.add_argument("--note", default="")
    draft = commands.add_parser("draft"); draft.add_argument("job_id"); draft.add_argument("--name", default="Candidate")
    tailored = commands.add_parser("tailor-resume")
    tailored.add_argument("job_id"); tailored.add_argument("--master-resume", type=Path); tailored.add_argument("--output", type=Path, required=True)
    prep = commands.add_parser("interview-prep")
    prep.add_argument("job_id"); prep.add_argument("--master-resume", type=Path); prep.add_argument("--output", type=Path, required=True)
    tracking = commands.add_parser("track")
    tracking.add_argument("job_id")
    tracking.add_argument("status", choices=["draft_ready", "review_required", "approved", "submitted", "interview", "rejected", "withdrawn"])
    tracking.add_argument("--note", default="")
    args = parser.parse_args()
    if args.command == "plan-source":
        workflow = plan_source(args.text, DeterministicProvider(), args.url)
        print(json.dumps({"source_kind": workflow.source_kind, "steps": workflow.steps, "needs_review": workflow.needs_review, "reason": workflow.reason, "confidence": workflow.confidence}, indent=2))
        return
    if args.command == "profile-init":
        paths = ProfilePaths(args.private_root, args.profile_id)
        paths.initialize(args.master_resume)
        print(f"Created local profile at {paths.directory}")
        return
    if args.command == "ai-status":
        ollama = OllamaProvider(model=args.model, base_url=args.ollama_url)
        gemini = GeminiProvider(model=args.gemini_model)
        if args.provider == "ollama":
            provider = ollama if ollama.health() else None
        elif args.provider == "gemini":
            provider = gemini if gemini.health() else None
        elif args.provider == "deterministic":
            provider = select_provider(prefer_ollama=False, prefer_gemini=False)
        else:
            provider = select_provider(model=args.model, base_url=args.ollama_url, prefer_gemini=True, gemini_model=args.gemini_model)
        print(f"Ollama: {'healthy' if ollama.health() else 'unavailable'} ({args.ollama_url}, model={args.model})")
        print(f"Gemini: {'configured' if gemini.health() else 'not configured'} (model={args.gemini_model})")
        print(f"Selected provider: {type(provider).__name__ if provider else 'unavailable'}; external actions remain disabled.")
        return
    if args.command == "inspect-link":
        if args.provider == "gemini":
            provider = GeminiProvider(model=args.gemini_model)
            if not provider.health():
                raise SystemExit("Gemini is not configured; set GEMINI_API_KEY or use --provider deterministic.")
        elif args.provider == "deterministic":
            provider = DeterministicProvider()
        else:
            provider = select_provider(prefer_ollama=False, prefer_gemini=True, gemini_model=args.gemini_model)
        try:
            result = inspect_public_link(args.url, provider)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        if args.save:
            if not args.database:
                raise SystemExit("--save requires --database PATH")
            evidence_repository = _repo(args.database)
            evidence_id = evidence_repository.save_evidence(result)
        else:
            evidence_id = None
        print(json.dumps({"evidence_id": evidence_id, "url": result.url, "final_url": result.final_url, "status": result.status, "content_type": result.content_type, "retrieved_bytes": result.retrieved_bytes, "classification": result.classification.__dict__, "extraction": result.extraction.__dict__ if result.extraction else None, "structured_fields": result.structured_fields, "provider_name": result.provider_name, "provider_model": result.provider_model, "error": result.error, "error_category": result.error_category}, indent=2, default=list))
        return
    if args.command == "evidence-list":
        evidence_repository = _repo(args.database)
        if args.json:
            print(json.dumps([dict(row) for row in evidence_repository.evidence(args.limit)], indent=2, default=list))
            return
        for row in evidence_repository.evidence(args.limit):
            print(f"{row['evidence_id']} | {row['status']} | {row['url']} | recovery={row['error_category'] or 'none'} | expires={row['expires_at'] or 'durable'}")
        return
    if args.command == "evidence-purge":
        evidence_repository = _repo(args.database)
        print(f"Expired evidence removed: {evidence_repository.purge_expired_evidence()}")
        return
    if args.command == "evidence-stats":
        print(json.dumps(_repo(args.database).evidence_stats(), indent=2))
        return
    if args.command == "evidence-decide":
        evidence_repository = _repo(args.database)
        evidence_repository.decide_evidence(args.evidence_id, args.decision, args.note)
        print("Evidence review decision recorded.")
        return
    if args.command == "evidence-promote":
        evidence_repository = _repo(args.database)
        added = evidence_repository.promote_approved_evidence(args.evidence_id, args.job_id, args.title, args.company_name, args.source_name)
        if args.score:
            job = next(record for record in evidence_repository.jobs() if record.job_id == args.job_id)
            evaluation = evaluate(job, evidence_repository.facts(), tuple(args.roles))
            evidence_repository.save_evaluation(evaluation)
            print(f"Canonical job {'created' if added else 'already existed'}; deterministic score={evaluation.score:.1f}; evidence approval preserved.")
        else:
            print(f"Canonical job {'created' if added else 'already existed'}; evidence approval preserved.")
        return
    if args.command == "review-server":
        review_repository = _repo(args.database)
        server = create_server(review_repository, args.host, args.port, args.master_resume)
        print(f"Review UI listening at http://{args.host}:{server.server_port}")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
        return
    if args.command == "catalog-status":
        profile_paths = ProfilePaths(args.private_root, args.profile) if args.profile else None
        catalog = args.catalog or (profile_paths.directory / "public_boards.json" if profile_paths else Path("public_boards.json"))
        entries = _load_catalog(catalog)
        print(json.dumps(_catalog_status(entries, _repo(args.database or (profile_paths.database if profile_paths else Path("job_hunt_agent.db")))), indent=2))
        return
    if args.command == "score-status":
        profile_paths = ProfilePaths(args.private_root, args.profile) if args.profile else None
        print(json.dumps(_score_status(_repo(args.database or (profile_paths.database if profile_paths else Path("job_hunt_agent.db")))), indent=2))
        return
    if args.command == "application-status":
        profile_paths = ProfilePaths(args.private_root, args.profile) if args.profile else None
        print(json.dumps(_repo(args.database or (profile_paths.database if profile_paths else Path("job_hunt_agent.db"))).application_stats(), indent=2))
        return
    if args.command == "integrity-status":
        profile_paths = ProfilePaths(args.private_root, args.profile) if args.profile else None
        print(json.dumps(_repo(args.database or (profile_paths.database if profile_paths else Path("job_hunt_agent.db"))).integrity_report(), indent=2))
        return
    if args.command == "submission-prepare":
        repository = _repo(args.database)
        job = next((item for item in repository.jobs() if item.job_id == args.job_id), None)
        if not job:
            raise SystemExit("Unknown job_id")
        handoff = prepare_handoff(job, args.platform)
        repository.save_submission_handoff(handoff.job_id, handoff.platform, handoff.payload, handoff.payload_sha256)
        print(json.dumps({"job_id": handoff.job_id, "platform": handoff.platform, "source_url": handoff.source_url, "payload": handoff.payload, "payload_sha256": handoff.payload_sha256, "review_required": True, "submitted": False}, indent=2))
        return
    if args.command == "draft-record":
        _repo(args.database).record_draft_version(args.job_id, args.draft_type, args.content_sha256, args.source_label)
        print("Draft version recorded.")
        return
    if args.command.startswith("gmail-") and not args.profile:
        raise SystemExit("Gmail commands require --profile PROFILE_ID")
    paths = ProfilePaths(args.private_root, args.profile) if args.profile else None
    database = args.database or (paths.database if paths else Path("job_hunt_agent.db"))
    repository = _repo(database)

    if args.command == "init":
        print(f"Initialized {database}; external actions are disabled.")
    elif args.command == "add-fact":
        repository.save_fact(ProfileFact(args.key, args.value, args.source, datetime.now(timezone.utc), args.confidence))
        print("Saved verified profile fact.")
    elif args.command == "import-master-resume":
        master_resume = MasterResume.load(args.file)
        for profile_fact in master_resume.facts():
            repository.save_fact(profile_fact)
        print(f"Imported {len(master_resume.facts())} verified master-resume facts.")
    elif args.command == "gmail-authorize":
        gmail_local.authorize(args.profile, args.credentials)
        print("Gmail read-only authorization is stored locally for this profile.")
    elif args.command == "gmail-status":
        print("Gmail is authorized for this profile." if gmail_local.is_authorized(args.profile) else "Gmail is not authorized for this profile.")
    elif args.command == "gmail-disconnect":
        gmail_local.disconnect(args.profile)
        print("Local Gmail authorization removed for this profile.")
    elif args.command == "gmail-scan-alerts":
        fetched, imported = scan_alerts(args.profile, repository, args.query, args.max_messages)
        print(f"Read {fetched} alert emails; imported {imported} new jobs.")
    elif args.command == "import-jobs":
        added = 0
        for data in json.loads(args.file.read_text(encoding="utf-8")):
            job = JobRecord(data["job_id"], data["title"], data["company_name"], args.source, data["source_url"], datetime.now(timezone.utc), data["description"], data.get("location"), data.get("work_mode"), data.get("employment_type"))
            added += repository.save_job(job)
        print(f"Imported {added} new jobs.")
    elif args.command == "ingest-public-board":
        jobs = fetch_public_board(args.provider, args.board)
        added = sum(repository.save_job(job) for job in jobs)
        print(f"Fetched {len(jobs)} public jobs; imported {added} new jobs.")
    elif args.command == "scan-public-boards":
        catalog = args.catalog or (paths.directory / "public_boards.json" if paths else Path("public_boards.json"))
        if not catalog.exists():
            raise SystemExit(f"Board catalog not found: {catalog}")
        entries = _load_catalog(catalog)
        fetched = imported = failed = 0
        for entry in entries:
            if not entry.get("enabled", True):
                continue
            provider, board_name = entry["provider"], entry["board"]
            jobs, failure = _fetch_catalog_entry(entry)
            if failure:
                failed += 1
                print(f"{entry.get('name', board_name)}: fetch failed safely ({failure}); continuing")
                continue
            fetched += len(jobs)
            added = sum(repository.save_job(job) for job in jobs)
            imported += added
            print(f"{entry.get('name', board_name)}: fetched {len(jobs)}; imported {added}")
        print(f"Scanned {fetched} public jobs; imported {imported} new jobs; failed boards={failed}.")
    elif args.command == "score":
        for job in repository.jobs():
            repository.save_evaluation(evaluate(job, repository.facts(), tuple(args.roles)))
        print("Scored jobs with keyword-v1; review the evidence before acting.")
    elif args.command == "queue":
        for row in repository.queue(args.threshold):
            print(f"{row['job_id']} | {row['score']:5.1f} | {row['title']} — {row['company_name']}")
    elif args.command == "decide":
        repository.decide(args.job_id, args.decision, args.note)
        print("Decision recorded.")
    elif args.command == "draft":
        job = next((record for record in repository.jobs() if record.job_id == args.job_id), None)
        if not job:
            raise SystemExit("Unknown job_id")
        print(cover_letter_draft(job, repository.facts(), args.name))
        repository.application(job.job_id, "review_required", "Draft generated locally")
    elif args.command in {"tailor-resume", "interview-prep"}:
        job = next((record for record in repository.jobs() if record.job_id == args.job_id), None)
        if not job:
            raise SystemExit("Unknown job_id")
        master_path = args.master_resume or (paths.master_resume if paths else None)
        if not master_path:
            raise SystemExit("Provide --master-resume or use --profile")
        master_resume = MasterResume.load(master_path)
        if args.command == "tailor-resume":
            output = tailored_resume_markdown(master_resume, job)
        else:
            output = interview_prep_markdown(master_resume, job)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
        repository.application(job.job_id, "review_required", f"{args.command} generated locally")
        print(f"Wrote {args.output}")
    elif args.command == "track":
        if args.status == "submitted":
            raise SystemExit("Submission is intentionally not available in this MVP.")
        repository.application(args.job_id, args.status, args.note)
        print("Status recorded.")


if __name__ == "__main__":
    main()
