# Conventions

## File Naming

| Note type | Pattern | Example |
|-----------|---------|---------|
| Incident | `YYYYMM_{시스템명} 오류 처리 {date}` | `202604_통합학사시스템 오류 처리 2026-04-10` |
| Improvement | `YYYYMM_{title}` | `202604_대학 검색 팝업 조회 기능 개선` |
| Work matter | `YYYYMM_{summary}` | `202604_학점교류 신청서류 간소화` |
| Training | `YYYY-MM-DD {name}` | `2026-04-10 정보보안 교육` |
| Project | `{identifier}` (folder name) | `2026_과업심의_API분리` |

### `10_Areas/` Depth Rules

- **Max 2 levels**: `10_Areas/{area}/` — notes live here, never deeper.
- **No attachments → single `.md`** at area root. Do not create a wrapper folder.
- **With attachments → folder per note**: folder name uses short `YYYYMM_{slug}` (slug ≤ 20 chars, 1–2 keywords). The note inside uses the full summary without `_` prefix.
- **Summary length**: keep `{summary}` ≤ 60 chars.

```
10_Areas/수업성적/
  202602_장바구니 기간 오등록 조치.md        ← no attachments → single file
  202602_장바구니장애학생/                    ← has attachments → folder (short slug)
    202602_장바구니 기간 장애학생지원 오등록수강인원 카운트 미변동.md
    조회결과.png
```

## Frontmatter

All notes follow the template frontmatter:

```yaml
---
type: work | change | project | training | routine | reference
status: open | in-progress | done | hold | active
change_type: incident | improvement   # only when type: change
---
```

## Tag System

### `#업무/` tags
- Classify work function / menu.
- Hierarchy: `#업무/{대분류}/{소분류}` — e.g. `#업무/수강신청`, `#업무/학적/생성`
- Detailed rules → `tag-normalizer` skill

### `#부서/` tags
- Identify requesting or related department.
- Hierarchy: `#부서/{단과대학}/{학과}` or `#부서/{부서명}` — e.g. `#부서/교무처`, `#부서/공과대학`
- When uncertain, delegate to `tag-validator` agent

### Tag authoring rules
- Always check `tag-normalizer` skill rules before writing tags on a new note.
- Never create a tag that doesn't exist without confirmation from `tag-validator` first.
- Review unresolved manual-check items in `plan.md` periodically.

## Wiki MOC (운영 도메인 허브)

`10_Areas`·`14_Changes` 노트가 누적되면 패턴이 생긴다. 패턴이 생기면 `_Wiki/topics/`에 도메인 MOC를 만들거나 갱신한다.

**언제 만드는가:**

| 조건 | 액션 |
|------|------|
| 동일 인시던트 유형 3회 이상 반복 | 도메인 MOC 반복 패턴 섹션에 추가/갱신 |
| 도메인 노트 20건 이상 누적 | 해당 도메인 MOC 신규 생성 |
| 시즌 사이클이 뚜렷한 도메인 | 캘린더 섹션 추가 |

**파일명:** `_Wiki/topics/{도메인}-운영-MOC.md`
예: `수업성적-운영-MOC.md`, `졸업-운영-MOC.md`, `예산관리-운영-MOC.md`

**표준 구조 (정적 + 라이브 하이브리드):** `_Wiki/contracts.md` → Operational MOC 섹션 참조.

**현재 생성된 MOC:**

Operational MOC (라이브 대시보드 포함):
- [[_Wiki/topics/수업성적-운영-MOC]]: 수업성적 (파일럿, 2026-05-01)

Topic MOC (정적 자료 인덱스, `_Wiki/topics/`):
- [[_Wiki/topics/규정-MOC]]: 규정·지침·법령
- [[_Wiki/topics/업무계획-MOC]]: 업무계획·국정과제
- [[_Wiki/topics/홈페이지-MOC]]: 홈페이지 운영·가이드라인
- [[_Wiki/topics/KORUS-MOC]]: 차세대 국립대 자원관리
- [[_Wiki/topics/교무회의-MOC]]: 교무회의 안건 인덱스
- [[_Wiki/topics/기타-MOC]]: 인재개발·계약·보도자료

## Templates

Always pick from `99_Template/` when creating a new note:

| Purpose | Template file |
|---------|--------------|
| Incident | `99_Template/_인시던트.md` |
| Improvement | `99_Template/_개선.md` |
| Work matter | `99_Template/_업무사안.md` |
| Training | `99_Template/_교육.md` |
| Routine | `99_Template/_루틴.md` |
| Project | `99_Template/_프로젝트.md` |
| Metadata rules | `99_Template/_메타데이터 규칙.md` |

> Removed (2026-05): `_업무노트.md` (daily), `_주간노트.md` (weekly) — archived in `90_Archive/daily-note/`
