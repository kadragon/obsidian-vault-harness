# Tasks

## Review Backlog

### PR #5 — [HARNESS] Improve due-date hook validation and weekly notes collection (2026-06-09)

- [ ] [debt] `check-template.py` skip list uses backslash substrings without path normalization — fix same as `check-todo-due-date.py` in this PR (source: review) — `check-template.py:16`
- [ ] [debt] `validate-tags.sh` python3 PATH guard absent — add `command -v python3` guard or migrate to script file (source: review) — `validate-tags.sh:298`
- [ ] [doc] hookify `tag-validator` loop-prevention mechanism not documented — clarify why agent re-write loop cannot occur (source: review) — `.claude/hookify.tag-validator.local.md:2`
- [ ] [debt] `.agents/skills` symlink reintroduced without explanation — confirm Developer Mode status; remove if still OFF (source: review) — `.agents/skills`
- [ ] [debt] `new_work_path.py` `find_duplicates` full rglob on every inbox run — add docstring noting future scaling concern (source: review) — `new_work_path.py:46`

### PR #6 — [HARNESS] update hooks, remove vault-orchestrate, sync docs (2026-06-14)

- [ ] [doc] Remove stale `vault-orchestrate` callout from `.claude/agents/obsidian-operator.md:62` — update invocation chain to direct orchestrator → obsidian-operator (source: pr-review-toolkit, agy, codex)
- [ ] [doc] Remove stale `vault-orchestrate` callout from `.claude/agents/tag-validator.md:147` — update to reflect direct delegation chain (source: pr-review-toolkit, agy, codex)
- [ ] [doc] Remove dangling `vault-orchestrate` row from `docs/runbook.md:84` — add note pointing to `docs/delegation.md` § Multi-step Chains (source: pr-review-toolkit, agy, codex)
- [ ] [doc] Remove `vault-orchestrate` from skill list in `_Wiki/topics/harness-engineering.md:59` (source: pr-review-toolkit)
- [ ] [doc] Align `docs/runbook.md` incident/improvement routing from "skill" to "agent" per updated skill metadata in `incident-analyze` and `improvement-plan` (source: codex)
