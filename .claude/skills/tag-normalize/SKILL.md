---
name: tag-normalize
description: "Workflow reference for tag-validator agent. Do NOT invoke directly — use the tag-validator agent instead. Contains normalization rules, mapping tables, and validation logic for #업무 and #부서 tags."
---

# Tag Normalizer — 태그 정규화 규칙

Define normalization rules for `#업무` and `#부서` tags across the vault.
Write tags inline in the `## 관련` section of note body — never in frontmatter.

Full mapping tables (area list, 부서명 매핑, 직급 분류, conversion examples) →
`references/tag-rules.md`

---

## `#업무` Tag Rules

### Format

```
#업무/{area}/{subarea}/{menu}
```

- `{area}`: 1st-level business domain (required) — one of the 18 allowed values in `references/tag-rules.md`
- `{subarea}`: 2nd-level detail (optional)
- `{menu}`: 3rd-level menu name (optional)

### Forbidden Prefixes

Do not insert these prefixes before the area segment:

`인트라넷/`, `부속/`, `행정/`, `학사/`, `공통/`, `시스템/`

Tags are based on **business domain**, not system module name (부속, 인트라넷), user type (학생서비스, 교수서비스), or high-level classification (학사, 공통).

### Special Character Rules

- Replace `()` with underscores: `관리_학과_` (correct), `관리(학과)` (incorrect)
- No spaces, `&`, or `+`
- Use `/` only as a hierarchy separator

---

## `#부서` Tag Rules

### Format

```
#부서/{부서명}/{직급}_{이름}
```

- 학과 조교 only: 4-level path — `#부서/학과/{학과명}/조교_{이름}`

### 직급 Rules (summary)

- 일반 행정직 → `주무관` (행정서기(보), 행정주사보, 전산서기보 등)
- 행정주사(6급) → `팀장` (업무팀장 직함 확인 시 `{업무}팀장`)
- 전문직·팀장급 이상 → keep original title

Full 직급 classification table → `references/tag-rules.md`

### Personnel Change Rules

- Do not use `P_` prefix
- Do not use `퇴직/` intermediate path — use last known department
- Past notes keep the department at time of writing; new notes use current department

---

## Automation — validate_tag.py

Delegate rule-based transformations (forbidden prefix removal, bracket substitution, 직급/부서명 mapping) to the script. Do not execute normalization logic directly.

```bash
# Single tag
python3 .claude/skills/tag-normalize/scripts/validate_tag.py '#업무/학사/수업성적/강좌관리'

# Multiple tags (stdin, one per line)
printf '%s\n' '#업무/공통/시스템/권한관리' '#부서/학사관리과/행정주사보_김영희' \
  | python3 .claude/skills/tag-normalize/scripts/validate_tag.py -

# JSON output
python3 .claude/skills/tag-normalize/scripts/validate_tag.py --json '<tag>'
```

스크립트 `[FIX]` 출력: 제안된 `→` 값을 적용한다.
예외: `행정주사` → 스크립트 출력 `팀장`; 실제 업무팀장 직함 파악 시 `{업무}팀장`으로 교체 (스크립트는 업무 맥락 미보유).

---

## `_Wiki/entities/` Authority Dictionary

When a system name or organization name is ambiguous, check `_Wiki/entities/` first:

```bash
ls _Wiki/entities/
```

If an entity note exists, apply its canonical name as the `#업무` area/subarea. Fall back to the allowed area table in `references/tag-rules.md` when no matching entity exists.

> Current status: entities dictionary has only 1 entry — the area table is the primary reference for most cases.

---

## Validation Checklist

### `#업무`

1. Is the 1st segment after `#업무/` one of the 18 allowed areas? (→ `references/tag-rules.md`)
2. Are forbidden prefixes (`인트라넷/`, `부속/`, `행정/`, `학사/`, `공통/`, `시스템/`) absent?
3. Are special characters `()`, spaces, `&`, `+` absent?
4. Is the area appropriate? (e.g., 공결신청 → 수업성적, 호실예약 → 시설물이용)
5. If `기타` is used, does it truly not fit any of the other 17 areas?

### `#부서`

1. Does it follow `#부서/{부서명}/{직급}_{이름}` format?
2. Is the department name using the canonical form? (→ `references/tag-rules.md`)
3. Does the 직급 follow the classification rules? (행정직 → 주무관, 6급 → 팀장)
4. Do 학과 조교 tags use the 4-level path `#부서/학과/{학과명}/조교_{이름}`?
5. Is the tag written in the note body (not frontmatter)?
