# Architecture README

## Logical components

1. **Profile service** - verified facts, preferences, constraints, and evidence.
2. **Source adapters** - permitted connectors that fetch jobs and preserve raw provenance.
3. **Normalizer and deduplicator** - canonical job records and stable identity keys.
4. **Scoring service** - structured evaluation with prompt/model/version metadata.
5. **Draft builder** - material drafts grounded in verified facts.
6. **Review queue** - human decisions, edits, approvals, and rejections.
7. **Action runner** - bounded, policy-checked external actions.
8. **Lifecycle tracker** - applications, statuses, messages, reminders, and outcomes.
9. **Audit and observability** - immutable event trail, metrics, errors, and run summaries.
10. **Local reasoning orchestrator** - model-assisted classification, evidence extraction, planning, and uncertainty routing; never an authority for facts or external actions.

## Design rules

- Components communicate through typed records and explicit status transitions.
- Retries must be idempotent and must not duplicate applications or messages.
- Raw source content and generated output are separated.
- Model outputs are untrusted until validated against schemas and profile facts.
- Local models may propose classifications, extraction steps, and drafts, but deterministic validators and policy checks decide what enters the canonical record.
- Memory is tiered: verified facts and decisions are durable; raw source content and reasoning traces are temporary and subject to retention rules.
- External actions are disabled by default in development and test environments.
- Secrets come from environment/secret storage, never committed files.

## Minimal state flow

`discovered -> normalized -> scored -> shortlisted -> draft_ready -> review_required -> approved -> submitted -> tracking`

Any state can transition to `rejected`, `blocked`, or `error` with a reason and timestamp. No component may silently skip a state.

