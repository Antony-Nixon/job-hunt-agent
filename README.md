# Job Hunt Agent

> **A review-first job search workspace for better decisions, not faster clicks.**

Job Hunt Agent is a human-supervised system for discovering relevant roles, evaluating fit, preparing truthful application materials, and tracking outcomes without giving up control of identity, claims, or consequential actions.

## The workflow

```text
Discover → Normalize → Deduplicate → Score → Review → Draft → Approve → Track → Learn
```

The project is designed around a simple rule: automation may reduce repetitive work, but the candidate remains the authority for facts, decisions, and external actions.

## What is implemented

- Structured candidate profiles and verified facts
- SQLite persistence with profile isolation
- Manual job import and provenance-aware records
- Deterministic evidence-based fit scoring
- Review decisions and audit events
- Fact-grounded resume, cover-letter, and interview-prep drafts
- Rendering and schema validation
- Retention and privacy controls
- Optional local and hosted foundations with guarded APIs
- A broad regression test suite

## Safety boundaries

- No fabricated qualifications, metrics, dates, or answers
- No CAPTCHA solving, access-control bypass, stealth, or platform evasion
- No application submission without an explicit approval checkpoint
- No secrets in source files, logs, or public documentation
- Model output is untrusted until validated against schemas and verified profile facts
- External actions are disabled by default in development and test environments

## Repository map

| Path | Purpose |
|---|---|
| `src/job_hunt_agent/` | Application modules and domain logic |
| `tests/` | Unit, contract, workflow, and safety regression tests |
| `01_GOVERNANCE/` | Safety, compliance, and operating rules |
| `02_PLAN/` | Implementation plans and milestones |
| `03_OPERATIONS/` | Current status, next actions, and operations notes |
| `04_ARCHITECTURE/` | Component boundaries and state flow |
| `05_DATA/` | Data contracts, profiles, provenance, and retention |
| `06_RUNBOOKS/` | Repeatable setup and operating procedures |
| `07_DECISIONS/` | Architecture decision records |
| `08_DEPLOYMENT/` | Deployment examples and migration material |
| `09_TOOLING/` | Import, verification, and maintenance scripts |
| `private/` | Local-only data; excluded from public release |

## Local setup

Create an isolated environment, install the project, and run the tests:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m pytest -q
```

The deterministic provider and local workflow are the safest starting points. Cloud providers, Gmail access, hosted APIs, and deployment secrets are optional and documented separately.

## Documentation starting points

- [Project overview](PROJECT_OVERVIEW.md)
- [Current status](03_OPERATIONS/CURRENT_STATUS.md)
- [Governance and safety](01_GOVERNANCE/SAFETY_AND_COMPLIANCE.md)
- [Architecture](04_ARCHITECTURE/README.md)
- [Local setup runbook](06_RUNBOOKS/LOCAL_SETUP.md)
- [Data and privacy](05_DATA/README.md)

## Public-release policy

The public project must exclude local databases, backups, resumes, profile data, OAuth credentials, API keys, session tokens, deployment secrets, and generated private output. The checked-in examples should contain placeholders only.

## Project status

This is an active local, review-first MVP. Job ingestion and assisted workflows are intentionally gated by permitted sources, validation, approval, and privacy controls.

## License

No license has been selected yet. Until a license is added, the repository remains source-available but does not grant broad reuse rights.

## Author

Built and maintained by Antony Nixon.

