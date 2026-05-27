# Eval Criteria

Note quality evaluation for `통합학사시스템` vault. Agent creates note (generator); separate evaluation pass checks it (evaluator). Separation prevents leniency drift.

## Criteria

### 1. Frontmatter Completeness (30%)

All required fields present and non-empty.

| Score | Description |
|-------|-------------|
| 5 | All required fields present, values conform to schema |
| 3 | 1 optional field missing |
| 1 | Required field missing (date, status, tags) |

Required fields by template:
- `_업무사안.md` — `date`, `status`, `tags`, `area`
- `_인시던트.md` — `date`, `status`, `tags`, `system`, `severity`
- `_개선.md` — `date`, `status`, `tags`, `target`
- `_교육.md` — `date`, `tags`, `title`

**How to test:** Read frontmatter, verify each required key has a non-empty value.

### 2. Tag Correctness (25%)

`#업무/` and `#부서/` tags follow `docs/conventions.md` → tag rules.

| Score | Description |
|-------|-------------|
| 5 | Tags pass `validate-tags.sh` and are semantically correct |
| 3 | Mechanical form correct; area assignment questionable |
| 1 | Forbidden prefix, unknown area, or tag missing entirely |

**How to test:** Run `bash .claude/hooks/validate-tags.sh` on note. Then verify area assignment matches note content.

### 3. Template Adherence (25%)

Note structure matches template from `99_Template/`.

| Score | Description |
|-------|-------------|
| 5 | All template sections present, heading hierarchy correct |
| 3 | 1 section missing or renamed |
| 1 | Multiple sections missing; bare text without template structure |

**How to test:** Compare note headings against template headings.

### 4. Wikilink Style (10%)

Internal links use plain `[[노트명]]`, never `![[embed]]` unless explicitly requested.

| Score | Description |
|-------|-------------|
| 5 | No embeds; all internal links are `[[link]]` style |
| 1 | `![[embed]]` present without explicit user request |

Note: Binary criterion — scores 2/3/4 not applicable. Either embeds exist (1) or they don't (5).

**How to test:** Grep for `![[` in note content.

### 5. Wiki Feedback Loop (10%)

Operational note feeds back into `_Wiki/` when domain threshold reached.

| Score | Description |
|-------|-------------|
| 5 | Domain has <20 notes — no MOC required, note complete |
| 5 | Domain has 20+ notes — MOC exists and this note is linked | ← both map to 5: threshold not triggered in first case |
| 2 | Domain has 20+ notes — MOC exists but note not registered |
| 1 | Domain has 20+ notes — MOC missing entirely |

**How to test:** Count notes in domain. If ≥20, check `_Wiki/topics/{도메인}-운영-MOC.md` exists and references this note.

## Pass Threshold

- All criteria ≥ 3 (no dimension broken)
- Weighted average ≥ 3.5

Below threshold → findings become fixes in same session before note is committed.

## Evaluator Protocol

1. Read note.
2. Grade each criterion with specific evidence (list findings first, score second).
3. Below threshold → fix and re-evaluate.
4. All pass → note done.

**Anti-pattern:** "Tag form looks fine so I'll give it a 4 even though the area is wrong." Score follows evidence, not vibes. Each criterion graded independently.
