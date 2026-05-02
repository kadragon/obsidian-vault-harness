# Mode: Review

내용이 다른 conflict 파일을 **원본 기준으로 그룹화**하여 haiku 서브에이전트에
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

## Step 2 — Haiku 서브에이전트 병렬 위임

각 그룹을 하나의 haiku 서브에이전트에 위임한다. 여러 그룹이 있으면 동시에
spawn하여 병렬 처리한다. 이를 통해 orchestrator가 큰 파일 본문을 직접 읽지 않고
요약만 받는다.

**각 서브에이전트에 주는 지시:**

```
다음 Obsidian 노트 파일들을 읽고 분석해줘.

원본: <original_path>
Conflict 파일:
  1. <conflict_path_1>  (타임스탬프: YYYYMMDD-HHMMSS, 기기: DEVICEID)
  2. <conflict_path_2>  (타임스탬프: ...)

분석 내용:
1. 원본과 각 conflict 사이의 차이점을 요약해줘.
   - 어느 섹션(frontmatter, 제목, 본문 등)이 바뀌었는지
   - 추가된 내용과 삭제된 내용이 무엇인지
   - 의미있는 변경인지, 메타데이터(날짜/태그)만 다른지 구분해줘.
2. 가장 유효해 보이는 버전에 대한 권장안을 제시해줘:
   - `keep_original`: 원본 유지, conflict 삭제
   - `replace_with_N`: conflict N번으로 원본 교체, 나머지 삭제
   - `merge_manually`: 양쪽 모두 의미 있는 변경 — 수동 병합 필요
3. 권장안 근거를 한 문장으로 설명해줘.

결과를 다음 형식으로 반환해줘:
{
  "original": "<path>",
  "conflicts": ["<path1>", "<path2>"],
  "summary": "<차이점 요약, 2-3문장>",
  "recommendation": "keep_original | replace_with_1 | replace_with_2 | merge_manually",
  "reason": "<근거 한 문장>",
  "confidence": "high | medium | low"
}
```

## Step 3 — 사용자 결정

모든 그룹의 분석이 완료되면 사용자에게 그룹별로 보고하고 선택을 받는다.

각 그룹 보고 형식:
```
### 그룹 A: 파일명.md

**요약**: <haiku 분석 요약>
**권장안**: keep_original (신뢰도: high)
**근거**: <이유>

**차이 미리보기** (첫 10줄):
  원본 마지막 수정: 2026-04-27 15:00
  Conflict 1 마지막 수정: 2026-04-27 06:53

**선택지**:
1. 권장안 수락 (keep_original)
2. 원본 유지, conflict 모두 삭제
3. Conflict 1로 교체
4. Conflict 2로 교체
5. 수동 병합 (이번엔 건너뜀)
```

## Step 4 — 선택 실행

사용자 선택에 따라 스크립트를 호출한다.

**원본 유지, conflict 삭제:**
```bash
python3 .claude/skills/syncthing-conflict-cleanup/scripts/conflict_cleanup.py delete "<conflict_path>" --apply
```
(conflict가 여러 개면 각각 호출)

**Conflict로 원본 교체:**
```bash
python3 .claude/skills/syncthing-conflict-cleanup/scripts/conflict_cleanup.py replace "<chosen_conflict>" --apply
# 나머지 conflict는 delete로 처리
python3 .claude/skills/syncthing-conflict-cleanup/scripts/conflict_cleanup.py delete "<other_conflict>" --apply
```

**수동 병합 (skip):**
해당 그룹을 건너뛰고 다음 그룹으로 넘어간다. 마지막에 "수동 병합 필요"로
분류된 항목 목록을 보고한다.

## Step 5 — Orphan 처리

`status: orphan` (원본이 없는 conflict) 항목을 별도 섹션으로 표시:

```
### 원본 없는 Conflict (Orphan)

| Conflict 파일 | 크기 | 날짜 |
|---------------|------|------|
| 파일명.sync-conflict-....md | 2.1 KB | 2026-04-27 |

선택지:
1. 원본 이름으로 복원 (conflict → 원본으로 rename)
2. 삭제
3. 건너뜀
```

복원 선택 시: 일반 `replace` 서브커맨드를 그대로 사용한다.
원본이 없으면 스크립트가 삭제 단계를 건너뛰고 rename만 수행하므로 orphan도 자동 처리된다.

## Step 6 — 최종 보고

```markdown
## Review 결과

| 항목 | 수치 |
|------|------|
| 검토한 그룹 | N |
| 원본 유지 처리 | A |
| Conflict로 교체 | B |
| 수동 병합 필요 (미처리) | C |
| Orphan 처리 | D |
```

미처리 항목이 있으면 경로 목록을 함께 보고한다.

## 비-md 파일 처리

그룹에 `status: non-text` 파일이 포함된 경우 haiku 위임 없이 orchestrator가
직접 처리: 크기/mtime만 비교하여 표로 출력하고 사용자가 직접 삭제/유지를 선택.
