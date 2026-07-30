---
name: vault-cleanup
description: "This skill should be used when the user asks to clean up, reorganize, or archive notes in the Obsidian vault — including 90_Archive document value review, duplicate removal, folder structure normalization ({area}/YYYY/YYYYMM_문서명/), category tag preservation, and archiving stale work notes from 10_Areas to 90_Archive. Korean triggers: '아카이브 정리', '문서 점검', '가치 없는 문서', '중복 정리', '시맨틱 중복', '비슷한 노트', 'deadlink', '폴더 구조 통일', '오래된 노트 정리', '볼트 청소', 'cleanup'. NOT for status flips on completed work (→ status-sync) or .sync-conflict files (→ syncthing-conflict-cleanup)."
---

# Vault Cleanup

Obsidian 볼트의 아카이브(`90_Archive/`)와 업무영역(`10_Areas/`)을 정리하는 스킬.

세 가지 모드를 제공하며, 사용자 요청에 따라 개별 또는 순차 실행한다. 모든 경로는 **볼트 루트 기준 상대경로**로 기술한다. 실행 전 `cd`로 볼트 루트에 진입한 뒤 진행한다.

## 작업 모드

| 모드 | 설명 | 트리거 키워드 | 세부 절차 |
|------|------|-------------|----------|
| **review** | 문서 가치 점검 → 삭제 후보 목록 제시 | 점검, 가치, 삭제 후보, 리뷰 | `references/mode-review.md` |
| **reorganize** | 폴더 구조 통일 + 중복 제거 | 구조 정리, 중복, 폴더 통일, reorganize | `references/mode-reorganize.md` |
| **archive** | 오래된 업무노트 아카이빙 | 오래된, 아카이브로, 이동 | `references/mode-archive.md` |
| **dedupe** | 시맨틱 중복 탐지 + wiki deadlink 점검 | 중복 노트, 비슷한 노트, 의미 중복, deadlink | `references/mode-dedupe.md` |
| **(전체)** | 위 4개를 순서대로 모두 실행 | 전체 정리, 대청소, full cleanup | 네 references 순차 |

사용자가 모드를 명시하지 않으면 어떤 모드를 원하는지 먼저 물어본다.

## 실행 흐름

1. 사용자 요청에서 모드를 확정한다 (명시 없으면 질문).
2. 해당 모드의 references 파일을 Read로 읽는다.
3. 그 안의 Step을 순서대로 실행한다.
4. 모드별 결과를 「보고 형식」 템플릿으로 요약한다.

## 결정론적 헬퍼 스크립트

구조 스캔, 중복 탐지, 오래된 문서 식별, 폴더 이동은 `scripts/reorg_archive.py`에 위임한다. LLM이 직접 bash/find/Python 스니펫을 쓰는 대신 스크립트 호출을 우선한다. 기본은 **dry-run**이며 실제 이동은 `--apply` 명시 시에만 실행된다.

```bash
# 1) 구조 스캔: orphan/ok/duplicate 분류
python3 .claude/skills/vault-cleanup/scripts/reorg_archive.py \
  scan-structure 90_Archive/areas/{area} --json

# 2) 1년 이상 지난 10_Areas 문서 찾기 (기본 cutoff = 오늘 - 12개월)
python3 .claude/skills/vault-cleanup/scripts/reorg_archive.py \
  find-stale 10_Areas --archive-root 90_Archive --json

# 3) orphan 폴더를 {area}/YYYY/ 하위로 이동 (dry-run)
python3 .claude/skills/vault-cleanup/scripts/reorg_archive.py \
  apply-reorg 90_Archive/areas/{area} --json
# 실제 이동:
python3 ... apply-reorg 90_Archive/areas/{area} --apply --json

# 4) 개별 오래된 폴더를 90_Archive로 이동 (dry-run)
python3 .claude/skills/vault-cleanup/scripts/reorg_archive.py \
  apply-archive 10_Areas/{area}/202304_... 90_Archive --apply

# 5) 무첨부 래퍼 폴더 스윕 (탐지 전용 — 이동 없음)
python3 .claude/skills/vault-cleanup/scripts/reorg_archive.py \
  find-bare-wrappers 10_Areas --json
```

스크립트가 **하지 않는 것**: `#업무/{area}/{category}` 태그 추가 (frontmatter 편집은 포맷 변형이 많아 LLM이 직접 검토·삽입). 이동 후 태그 작업은 별도 단계로 진행한다.

## 안전 규칙

1. **삭제/이동 전 항상 목록을 먼저 보여주고 사용자 승인을 받는다.**
2. DRY RUN으로 먼저 결과를 보여주고, 실제 실행은 별도 단계.
3. `90_Archive` 내 파일만 삭제한다 (`10_Areas`, `14_Changes` 등은 삭제 대상 아님).
   **삭제는 `rm -rf`가 아니라 `reorg_archive.py purge`로 `<볼트>/.trash/`에 이동**한다 (노트는 git-ignore라 hard delete 복구 불가). 사용자가 `.trash`를 확인 후 직접 비운다.
4. 빈 폴더는 작업 완료 후 자동 정리.
5. 작업용 임시 Python 스크립트는 작업 종료 후 삭제한다.

## 보고 형식

각 모드 실행 후 결과를 요약 테이블로 보고한다:

```markdown
## 정리 결과

| 항목 | 수치 |
|------|------|
| 정리 전 문서 수 | N |
| 삭제된 문서 | M |
| 이동된 문서 | K |
| 정리 후 문서 수 | N-M |
```

## Additional Resources

- **`references/mode-review.md`** — 문서 가치 점검, haiku 에이전트 배포, 삭제 승인 절차
- **`references/mode-reorganize.md`** — 구조 분석, 중복 탐지, 재구조화, 태그 보존
- **`references/mode-archive.md`** — 1년 경과 대상 식별, 이동 실행
- **`references/mode-dedupe.md`** — 시맨틱 중복 탐지, wiki deadlink 점검
- **`scripts/reorg_archive.py`** — 결정론적 스캔·이동 헬퍼
