# Enforcement

Mechanical layers that prevent Golden Principle violations.

## Current Status

Notes-only vault — no git pre-commit / CI layer. Only Claude Code PostToolUse hooks are applicable.

| Golden Principle | Enforcement method | Status |
|-----------------|-------------------|--------|
| #1 Existing notes immutable | AGENTS.md rule + Hard Stop | Doc-enforced |
| #2 Follow templates | `tag-validator` agent side-effect check | Doc-enforced |
| #3 Normalize tags | `validate-tags.sh` PostToolUse hook (mechanical) | Shell-enforced |
| #4 Folder rules | AGENTS.md rule | Doc-enforced |
| #5 InfoBox via skill | AGENTS.md delegation rule | Doc-enforced |

## Tag Validation Hooks

### Active: `validate-tags.sh` (mechanical)

`.claude/hooks/validate-tags.sh`, registered in `settings.local.json` as `PostToolUse` on `Write|Edit`. Regex-based checks:

- Forbidden `#업무/` prefixes (e.g., `#업무/인트라넷/`, `#업무/학사/`)
- Parentheses in `#업무/` tags
- Unknown areas (outside allowed list)
- `#부서/` tags appearing in frontmatter

Warning-only (does not block). Zero token cost.

### Dormant: `hookify.tag-validator.local.md` (agent delegation)

Defined but `enabled: false`. Would delegate to `tag-validator` agent in `validate` mode on every `.md` write containing `#업무/` or `#부서/`. Disabled because:

- Duplicates mechanical checks already covered by shell hook
- Triggers agent call on every note edit (token cost)
- Loop risk if the agent itself writes to the file

Activate only when GP #3 reinforcement threshold is met (see below).

## Reinforcement Order

Add enforcement layers only when a violation actually recurs (avoid over-engineering):

1. GP #3 **semantic** tag errors (correct mechanical form, wrong area assignment) repeat 2+ times → enable `hookify.tag-validator.local.md`
2. GP #2 template non-use repeats → add PostToolUse `Write` hook for template check
3. GP #4 folder rule violations repeat → add PostToolUse `Write` hook for path validation
