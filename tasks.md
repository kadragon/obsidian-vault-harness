# Tasks

## Review Backlog

### PR #5 — [HARNESS] Improve due-date hook validation and weekly notes collection (2026-06-09)

- [ ] [debt] `check-template.py` skip list uses backslash substrings without path normalization — fix same as `check-todo-due-date.py` in this PR (source: review) — `check-template.py:16`
- [ ] [debt] `validate-tags.sh` python3 PATH guard absent — add `command -v python3` guard or migrate to script file (source: review) — `validate-tags.sh:298`
- [ ] [doc] hookify `tag-validator` loop-prevention mechanism not documented — clarify why agent re-write loop cannot occur (source: review) — `.claude/hookify.tag-validator.local.md:2`
- [ ] [debt] `.agents/skills` symlink reintroduced without explanation — confirm Developer Mode status; remove if still OFF (source: review) — `.agents/skills`
- [ ] [debt] `new_work_path.py` `find_duplicates` full rglob on every inbox run — add docstring noting future scaling concern (source: review) — `new_work_path.py:46`

