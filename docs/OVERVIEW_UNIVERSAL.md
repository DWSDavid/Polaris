# Universal Project Overview: Memory and Backtracking

This standard applies to every project, not only Polaris.

## Principle

Every serious project needs a durable memory layer. Chat history alone is not enough. The project should be able to answer:

- What changed?
- Why did it change?
- Which version worked before?
- What data, prompt, config, or model behavior caused the current result?
- How do we return to a previous working version?

## Required memory layers

1. Git memory

Use branches, commits, tags, and pushed remotes as the source of truth for code. Commit messages should describe the change, not just the files touched.

2. Progress memory

Keep a project-local update file such as `docs/UPDATE_AND_HISTORY_PROGRESS.md`. Each meaningful milestone should record date, branch, decision, validation, deploy impact, local-only files, and next steps.

3. Product and architecture memory

Keep specs, plans, implementation notes, and decision records in the repo. Do not leave important reasoning only in a chat window.

4. Runtime and user memory

If the product learns from usage, design an explicit memory layer. This may be RAG, embeddings, event logs, saved sessions, audit trails, or a simpler structured history table. Store source, timestamp, user/project scope, version, and retrieval path.

5. Rollback memory

Before risky changes, know how to go back. Use git history for code, database backups or migrations for state, and deploy/version notes for production. A project is not stable unless a previous working version can be identified and restored.

## Minimum checklist for future projects

- `README.md` explains setup and run commands.
- `docs/UPDATE_AND_HISTORY_PROGRESS.md` records project movement over time.
- `docs/OVERVIEW_UNIVERSAL.md` or an equivalent local standard explains memory and rollback expectations.
- Secrets and private data are gitignored and documented as hand-carried or dashboard-managed.
- Tests or smoke checks are listed with the last known validation result.
- Any AI/RAG behavior records what was retrieved, from where, and under which version.

