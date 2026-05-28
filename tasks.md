# Tasks

## Review Backlog

### PR #3 — [HARNESS] Add settings, hooks, docs, and skill updates (2026-05-27)

- [x] [debt] `AGENTS.md` workflow gate paragraph has no heading — easy to miss; consider `## Workflow Gates` section (source: review) — `AGENTS.md`
- [x] [debt] Hook gap: `check-todo-due-date.ps1` only fires on `Write`, not `Edit` for existing notes (source: review) — already fixed in settings.json (`"matcher": "Write|Edit"`)
- [x] [constraint] `.agents/skills` text file (mode 100644) deleted in PR #4 — `.agents/` dir removed; symlink approach abandoned (Developer Mode OFF, skills resolved globally) (source: pr-review-toolkit, codex)

### PR #4 — [HARNESS] Add eval-criteria.md references to delegation docs (2026-05-28)

- [x] [doc] Add evaluator-pass gate to `delegation.md` routing table — Background Gate row: `Note created by agent` | `evaluator pass (see docs/eval-criteria.md)` | `note path` (source: pr-review-toolkit)
