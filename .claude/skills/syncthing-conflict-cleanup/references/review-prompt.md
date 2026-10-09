# Review 위임 프롬프트 템플릿 (syncthing-conflict-cleanup mode-review Step 2용)

각 그룹을 하나의 서브에이전트에 위임한다. 여러 그룹이 있으면 동시에
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

## 그룹 보고 형식 (Step 3용)

```
### 그룹 A: 파일명.md

**요약**: <분석 요약>
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

## Orphan 표시 형식 (Step 5용)

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

## 최종 보고 형식 (Step 6용)

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
