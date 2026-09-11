# AgriAI agent guide

## Agent skills

### Issue tracker

Track implementation work and defects in GitHub Issues for `QuangTapcode/AI-Agriculture`. See `docs/agents/issue-tracker.md`.

### Triage labels

Use the canonical `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, and `wontfix` labels. See `docs/agents/triage-labels.md`.

### Domain docs

This repository uses multiple contexts. Start with `CONTEXT-MAP.md`, then read the context for the subsystem being changed. See `docs/agents/domain.md`.

## Product rules

- Production UI must never present mock, sample, demo, estimated, or invented values as real data.
- Quantitative data must include its source and update state. Missing data is shown as unavailable, never replaced with zero.
- Use the Prototype A “Field Command” visual direction and the shared design tokens.
- Complete and verify one page before moving to the next page in the delivery order.
- Preserve Vietnamese text as UTF-8.

## Engineering rules

- Follow red-green-refactor for behavior changes.
- Run frontend tests and the production build before committing frontend work.
- Do not commit `deploy/agriai-demo-pages/_worker.js` unless the task explicitly changes the active tunnel.
