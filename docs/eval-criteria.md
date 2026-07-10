# Eval Criteria

Note quality evaluation for `통합학사시스템` vault. Agent creates note (generator); separate evaluation pass checks it (evaluator). Separation prevents leniency drift.

## Criteria

### 1. Frontmatter Completeness (30%)

All required fields present and non-empty.

| Score | Description |
|-------|-------------|
| 5 | All required fields present, values conform to schema (`type`, `status` enum-valid) |
| 3 | `change_type` missing on a change note (incident/improvement) |
| 1 | `type` or `status` missing, or `status` not in enum |

Required frontmatter by note kind (per `99_Template/_메타데이터 규칙.md` — `date created`/`date modified` are Linter-managed, NOT authored; 태그는 본문 `## 관련` 인라인, frontmatter 아님):
- `_업무사안.md` (work) — `type: work`, `status`
- `_인시던트.md` (change) — `type: change`, `change_type: incident`, `status`
- `_개선.md` (change) — `type: change`, `change_type: improvement`, `status`
- `_교육.md` (training) — `type: training`, `status`

`status` 허용값: `open | in-progress | hold | closed | active` (그 외는 위반).

**How to test:** `python3` 또는 Read로 frontmatter 파싱 — `type` 존재, `status` enum 일치, change 노트는 `change_type` 확인. `check-template.py` 훅과 동일 기준.

### 2. Tag Correctness (25%)

`#업무/` and `#부서/` tags follow `docs/conventions.md` → tag rules.

| Score | Description |
|-------|-------------|
| 5 | Tags pass `validate-tags.sh` and are semantically correct |
| 3 | Mechanical form correct; area assignment questionable |
| 1 | Forbidden prefix, unknown area, or tag missing entirely |

**How to test:** Run `bash .claude/hooks/validate-tags.sh` on note. Then verify area assignment matches note content.

### 3. Template Adherence (25%)

Note structure matches template from `99_Template/`. **`## 관련 문서`는 content-conditional 섹션** — 실제 관련 문서(첨부·설계 문서·위키 등)가 있을 때만 포함한다. 근거 없어 생략한 것은 "누락"으로 채점하지 않는다.

| Score | Description |
|-------|-------------|
| 5 | All required sections present, heading hierarchy correct (content-conditional 섹션은 근거 없으면 생략되어 있어도 5점) |
| 3 | 1 required section missing or renamed (content-conditional 섹션 생략은 해당 안 됨) |
| 1 | Multiple required sections missing; bare text without template structure; **또는 `- [[ ]]` 같은 빈 wikilink 플레이스홀더가 남아있음(생략하지 않고 억지로 채운 흔적)** |

**How to test:** Compare note headings against template headings, excluding `## 관련 문서`(및 근거 없는 다른 content-conditional 섹션) when genuinely empty. Grep note body for `\[\[\s*\]\]` — any match is an automatic 1.

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
