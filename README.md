# Job Hunt Agent

> **A review-first job search system for better decisions, not faster clicks.**

Job Hunt Agent is a human-supervised system for discovering relevant roles, evaluating fit, preparing truthful application materials, and tracking outcomes without giving up control of identity, claims, or consequential actions.

## Workflow

```text
Discover → Normalize → Deduplicate → Score → Review → Draft → Approve → Track → Learn
```

Automation reduces repetitive work; the candidate remains the authority for facts, decisions, and external actions.

## Design principles

- Evidence before claims
- Human approval before consequential actions
- Deterministic, explainable scoring
- Provenance and auditability
- Privacy by default
- Safe failure when data or validation is incomplete

## Safety boundaries

- No fabricated qualifications, metrics, dates, or answers
- No CAPTCHA solving, access-control bypass, stealth, or platform evasion
- No application submission without an explicit approval checkpoint
- No secrets, resumes, contact records, or generated private material in the public repository
- Model output is untrusted until validated against verified facts and schemas
- External actions are disabled by default in development and test environments

## Public repository map

| Path | Purpose |
|---|---|
| `PROJECT_OVERVIEW.md` | Product scope and intended workflow |
| `01_GOVERNANCE/` | Public safety and operating rules |
| `04_ARCHITECTURE/` | System boundaries and state flow |
| `05_DATA/` | Public data-handling policy and schema guidance |
| `07_DECISIONS/` | Architecture decision records |
| `config.example.toml` | Non-secret configuration shape |
| `pyproject.toml` | Python project metadata and tooling direction |

This public snapshot intentionally contains design documentation and safe configuration examples only. Private profiles, resumes, databases, credentials, deployment material, and local operational notes remain outside the public repository.

## Local development

The complete working tree is maintained privately while the public release surface is being scrubbed and modularized. Before publishing implementation code, each file must pass the project’s public-release checklist for personal-data, secret, and internal-workflow leakage.

## Documentation

- [Project overview](PROJECT_OVERVIEW.md)
- [Governance and safety](01_GOVERNANCE/SAFETY_AND_COMPLIANCE.md)
- [Architecture](04_ARCHITECTURE/README.md)
- [Public data policy](05_DATA/README.md)
- [Configuration example](config.example.toml)

## Project status

Active private MVP with a public architecture snapshot. The next release milestone is a minimal, reproducible code path containing only sanitized examples and tests.

## License

No license has been selected yet. Until a license is added, this repository is source-available but does not grant broad reuse rights.
