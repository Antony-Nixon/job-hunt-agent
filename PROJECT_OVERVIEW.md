# Job Hunt Agent Project Overview

## Purpose

The Job Hunt Agent is a human-supervised system for finding relevant jobs, evaluating fit, preparing truthful application materials, assisting with approved submissions, tracking application status, and learning from outcomes.

It is designed to reduce repetitive work while keeping identity, claims, personal data, and consequential external actions under the user's control.

## Current state

The repository contains a local, review-first MVP: validated records, SQLite persistence, manual JSON import, provenance-aware deduplication, deterministic evidence-based scoring, decisions and audit events, fact-grounded draft text, and local lifecycle tracking. No live job ingestion or application submission is active.

See [[03_OPERATIONS/CURRENT_STATUS|Current Status]] for the latest milestone state.

## End-to-end workflow

`Discover -> Normalize -> Deduplicate -> Score -> Review -> Draft -> Approve -> Submit -> Track -> Learn`

- **Discover:** collect jobs only from permitted sources and preserve provenance.
- **Normalize:** convert source data into a canonical job record.
- **Deduplicate:** prevent repeated jobs and duplicate actions.
- **Score:** evaluate fit using structured evidence, confidence, and a versioned rubric.
- **Review:** let the user approve, reject, edit, or defer recommendations.
- **Draft:** generate tailored materials from verified candidate facts only.
- **Approve:** verify target, files, answers, and destination.
- **Submit:** perform only explicitly approved and policy-compliant external actions.
- **Track:** maintain application status, reminders, messages, and outcomes.
- **Learn:** use results to improve preferences and scoring without rewriting history.

## Main modules

| Module | Responsibility |
|---|---|
| Profile | Verified candidate facts, preferences, constraints, and evidence |
| Sources | Permitted job connectors and raw-content provenance |
| Normalization | Canonical records, validation, and deduplication |
| Scoring | Explainable fit evaluation and human override |
| Drafting | Tailored resume and cover-letter drafts |
| Review | Approval queue and audit events |
| Actions | Bounded external actions; disabled by default |
| Tracking | Application lifecycle, inbound events, reminders, and metrics |
| Observability | Run summaries, errors, retries, audit trail, and privacy controls |

## Milestones

1. **M0 Foundation:** repository, governance, profile/data contracts, tests, and configuration.
2. **M1 Job ingestion:** permitted sources, normalized records, provenance, and deduplication.
3. **M2 Fit scoring:** structured evidence, confidence, rubric versioning, and override.
4. **M3 Material drafts:** truthful tailored drafts and rendering checks.
5. **M4 Review queue:** human decisions, edits, approvals, and audit records.
6. **M5 Assisted submission:** one approved, policy-compliant submission path.
7. **M6 Lifecycle tracking:** statuses, reminders, inbound events, and outcome metrics.
8. **M7 Hardening:** recovery, privacy, monitoring, regression tests, and complete runbooks.

## Non-negotiable safeguards

- No fabricated qualifications, metrics, dates, answers, or work authorization.
- No CAPTCHA solving, access-control bypass, stealth, or platform-evasion features.
- No submission or contact without the required approval checkpoint.
- No secrets in source files or logs.
- Minimize, protect, retain, export, and delete personal data deliberately.
- Make every recommendation and external action traceable.

## Documentation map

- `AGENT_INSTRUCTIONS.md` - how the agent loads context and keeps documentation current.
- `00_INDEX.md` - navigation and folder map.
- `01_GOVERNANCE/` - operating rules and safety boundaries.
- `02_PLAN/MASTER_IMPLEMENTATION_PLAN.md` - scope, phases, gates, and success measures.
- `03_OPERATIONS/` - workflow and current status.
- `04_ARCHITECTURE/` - components and state flow.
- `05_DATA/` - entities, provenance, privacy, and retention.
- `06_RUNBOOKS/` - repeatable operating procedures.
- `07_DECISIONS/` - decisions and rationale.

## Next actions

1. Complete `05_DATA/PROFILE_TEMPLATE.md` and enter only verified facts.
2. Install a working Python runtime and run the test suite.
3. Select permitted job sources and access methods.
4. Validate the scoring rubric against owner-reviewed real jobs before adding any live adapter.

