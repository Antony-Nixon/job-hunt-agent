# Public data policy

This public repository contains schemas, examples, and design rules only. It does not contain a real candidate profile, resume, contact record, job database, session token, OAuth credential, or generated application material.

## Data boundaries

- Verified candidate facts belong in a private profile store.
- Job-source content must preserve provenance and retention rules.
- Generated drafts must be grounded in approved facts.
- Secrets must come from environment or secret storage.
- Local databases, backups, exports, and private outputs remain outside the public repository.

## Example data

Examples use fictional names, organizations, and addresses. They are test fixtures, not real candidate information.

## Privacy principles

- Collect the minimum data needed for the workflow.
- Keep identity and contact data separate from public source code.
- Minimize retention of raw source content and reasoning traces.
- Make export and deletion deliberate operations.
- Never publish personal data merely because it exists in a local development folder.
