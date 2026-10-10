# Mode: Review

내용이 다른 conflict 파일을 **원본 기준으로 그룹화**하여 서브에이전트에
병렬 분석을 위임하고, 사용자 선택에 따라 처리한다.

## Step 1 — 검토 대상 수집

scan 결과에서 `status: different` 항목을 원본별로 그룹화한다.
(이미 scan을 실행했다면 결과를 재사용. 아니라면 먼저 scan 실행.)

그룹 예시:
```
그룹 A: 원본 10_Areas/.../파일.md
  └─ conflict 1: 파일.sync-conflict-20260427-065342-YTJXM34.md
  └─ conflict 2: 파일.sync-conflict-20260427-155346-WERFXNH.md
```

## Step 2 — 서브에이전트 병렬 위임

각 그룹을 하나의 서브에이전트에 위임한다. 여러 그룹이 있으면 동시에
spawn하여 병렬 처리한다. 이를 통해 orchestrator가 큰 파일 본문을 직접 읽지 않고
요약만 받는다.

지시문·반환 형식·보고 템플릿은 `references/review-prompt.md`를 그대로 쓴다.

## Step 3 — 사용자 결정

모든 그룹의 분석이 완료되면 사용자에게 그룹별로 보고하고 선택을 받는다.
그룹 보고 형식은 `references/review-prompt.md` §그룹 보고 형식을 쓴다.

## Step 4 — 선택 실행

사용자 선택에 따라 스크립트를 호출한다.

**원본 유지, conflict 삭제:**
```bash
python3 .claude/skills/syncthing-conflict-resolve/scripts/conflict_cleanup.py delete "<conflict_path>" --apply
```
(conflict가 여러 개면 각각 호출)

**Conflict로 원본 교체:**
```bash
python3 .claude/skills/syncthing-conflict-resolve/scripts/conflict_cleanup.py replace "<chosen_conflict>" --apply
# 나머지 conflict는 delete로 처리
python3 .claude/skills/syncthing-conflict-resolve/scripts/conflict_cleanup.py delete "<other_conflict>" --apply
```

**수동 병합 (skip):**
해당 그룹을 건너뛰고 다음 그룹으로 넘어간다. 마지막에 "수동 병합 필요"로
분류된 항목 목록을 보고한다.

## Step 5 — Orphan 처리

`status: orphan` (원본이 없는 conflict) 항목을 별도 섹션으로 표시한다.
표시 형식은 `references/review-prompt.md` §Orphan 표시 형식을 쓴다.

복원 선택 시: 일반 `replace` 서브커맨드를 그대로 사용한다.
원본이 없으면 스크립트가 삭제 단계를 건너뛰고 rename만 수행하므로 orphan도 자동 처리된다.

## Step 6 — 최종 보고

보고 형식은 `references/review-prompt.md` §최종 보고 형식을 쓴다.
미처리 항목이 있으면 경로 목록을 함께 보고한다.

## 비-md 파일 처리

그룹에 `status: non-text` 파일이 포함된 경우 위임 없이 orchestrator가
직접 처리: 크기/mtime만 비교하여 표로 출력하고 사용자가 직접 삭제/유지를 선택.
