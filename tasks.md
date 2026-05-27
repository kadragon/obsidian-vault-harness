# Tasks

## Review Backlog

### PR #3 — [HARNESS] Add settings, hooks, docs, and skill updates (2026-05-27)

- [ ] [debt] `AGENTS.md` workflow gate paragraph has no heading — easy to miss; consider `## Workflow Gates` section (source: review) — `AGENTS.md`
- [ ] [debt] Hook gap: `check-todo-due-date.ps1` only fires on `Write`, not `Edit` for existing notes (source: review) — `.claude/hooks/check-todo-due-date.ps1:3`
- [ ] [constraint] `.agents/skills` is text file (mode 100644), not symlink (mode 120000) — proper symlink requires Windows Developer Mode or admin; enable Developer Mode then: `cd .agents && ln -s ../.claude/skills skills && git add skills` (source: pr-review-toolkit, codex)
