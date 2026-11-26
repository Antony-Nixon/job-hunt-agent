# Safety and Compliance

## Non-negotiable boundaries

- No false claims or fabricated application answers.
- No submission without an explicit, visible approval step unless the owner later defines and approves a narrower trusted workflow.
- No credential harvesting, password storage in source files, or secret leakage in logs.
- No bypassing CAPTCHAs, access controls, bot protections, paywalls, or platform restrictions.
- Respect robots, terms of service, rate limits, privacy obligations, and applicable employment laws.
- Do not infer sensitive demographic or protected characteristics for targeting or disclosure.
- Store only the personal data needed for the workflow, with retention and deletion procedures.

## Risk tiers

| Tier | Example | Default control |
|---|---|---|
| Low | Parse a public job page; normalize a title | Automated with logs |
| Medium | Score fit; draft a resume; send an alert | Automated, reviewable, human override |
| High | Answer a custom screening question; upload documents | Human review required |
| Critical | Submit an application; contact a recruiter; disclose sensitive data | Explicit approval immediately before action |

## Review checklist

Before enabling an external action, verify the target, fields, files, identity, answers, destination, platform permission, and audit log. If any item is unclear, stop.

