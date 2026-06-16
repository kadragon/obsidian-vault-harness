# Vault Architecture

## Numbering Bucket Reference

신규 폴더 추가 시 아래 버킷 체계를 따른다.

| 버킷 | 의미 | 현재 폴더 |
|------|------|----------|
| `0x` | 캡처 레이어 | `01_Inbox` |
| `1x` | 활성 업무 레이어 (Areas·Projects·Routines·Changes·Reference) | `10_Areas`, `12_Projects`, `11_Routines`, `14_Changes`, `19_Reference` |
| `2x` | 지식·학습 레이어 | `20_Training` |
| `8x` | (현재 미사용 — 예비) | — |
| `9x` | 메타·종결 레이어 | `90_Archive`, `99_Template` |
| `_`  | 시스템 레이어 (agent-facing, not notes) | `_Wiki`, `docs` |

1x 버킷 내 갭(`11`, `15–18`)은 미래 도메인 확장을 위해 예비.

## Folder Map

```
ObsidianVault/
├── _Wiki/                 # Vault-wide LLM wiki layer (index·log·entities·topics·syntheses·lint)
├── 01_Inbox/              # Unprocessed documents — process via inbox-process skill
│   ├── action/            # 공문·요청 → 10_Areas/ 업무사안 노트
│   ├── reference/         # PDF·HWPX·웹 클립 → 19_Reference/_Sources + _Wiki
│   └── (root)             # 분류 모호 시 임시 drop zone (스킬이 분류 제안)
├── 10_Areas/              # Work matter notes by domain (max 2 levels deep)
│   ├── 개발공통/
│   ├── 교직/
│   ├── 구전자문서/
│   ├── 기타/
│   ├── 수강신청/
│   ├── 수업성적/
│   ├── 예산관리/
│   ├── 과업심의/
│   ├── 전임교원공채/
│   ├── 졸업/
│   └── ...
├── 12_Projects/           # Active projects (folder-per-project only)
├── 11_Routines/           # Recurring task routines (Nexacro·SSL·UbiServer renewal, etc.)
├── 14_Changes/            # System change records
│   ├── incident/          # Incidents by year
│   └── improvement/       # Improvements by year
├── 19_Reference/          # Reference materials (raw sources only)
│   ├── _Assets/
│   └── _Sources/
├── 20_Training/           # Education/training notes
├── 90_Archive/            # Completed/expired notes (no agent-created files)
└── 99_Template/           # Note templates
```

## Note Placement

| Note type | Location |
|-----------|----------|
| Incident (error) | `14_Changes/incident/{year}/` |
| Improvement plan | `14_Changes/improvement/{year}/` |
| Work matter (공문·요청) | `10_Areas/{업무영역}/` |
| 과업심의 (회차별 위원회) | `10_Areas/과업심의/` |
| Training record | `20_Training/` |
| New project | `12_Projects/{project-name}/` (folder required) |
| Recurring routine | `11_Routines/` |
| Source material | `19_Reference/_Sources/` |
| Wiki (entity/topic/synthesis) | `_Wiki/{entities,topics,syntheses}/` |

## Archive Placement

`90_Archive/`는 원천 폴더명을 그대로 미러링한다. 보관 시 아래 경로로 이동:

| 원천 | Archive 경로 |
|------|-------------|
| `10_Areas/{domain}/` | `90_Archive/areas/{domain}/` |
| `12_Projects/{project}/` | `90_Archive/projects/{project}/` |
| `11_Routines/{name}/` | `90_Archive/routines/{name}/` |
| `14_Changes/incident/{year}/` | `90_Archive/changes/incident/{year}/` |
| `14_Changes/improvement/{year}/` | `90_Archive/changes/improvement/{year}/` |
| `20_Training/{year}/` | `90_Archive/training/{year}/` |
| `19_Reference/_Sources/` 개별 노트 | `90_Archive/reference/` |
| `00_DailyNote/` (종료됨) | `90_Archive/daily-note/` ✅ |

`90_Archive/changes/`, `90_Archive/training/`, `90_Archive/reference/` 는 agent가 vault-cleanup skill을 통해 생성한다.

## Constraints

- No files created in `90_Archive/`.
- No loose `.md` files in `12_Projects/` — folders only.
- `10_Areas/` depth max 2 levels. No attachment → single `.md` at area root. With attachment → `YYYYMM_{slug}/` folder containing `YYYYMM_{summary}.md` + attachments.
- Documents in `01_Inbox/` are never processed directly; use `inbox-process` skill. The skill dispatches to action (→ `10_Areas/`) or reference (→ `19_Reference/_Sources`·`_Wiki`) based on subfolder or content-based triage.
