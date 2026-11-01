# 발송 기록 입력과 실행

`scripts/record_dispatch.py`는 확정된 사실을 기존 소스 노트의 할 일·현황에 기록한다.
발송 사실, 기존 항목 선택, 후속 업무 필요 여부는 대화와 원문에서 먼저 판단한다.
스크립트는 유사한 업무를 찾아 선택하거나 수신자·공문번호·기한을 추정하지 않는다.

## 입력 JSON

스크래치 경로에 아래 형식의 JSON을 저장한다. 문자열은 줄바꿈 없는 한 줄이다.

```json
{
  "event_id": "dispatch-20261101-001",
  "note": "10_Areas/개발공통/예시 업무.md",
  "dispatched_on": "2026-10-31",
  "recorded_on": "2026-11-01",
  "summary": "학사관리과에 공문 발송(정보전산원-123) — 개선 결과 안내",
  "task_line": "> - [ ] 학사관리과에 공문 발송",
  "follow_up": {
    "text": "학사관리과 회신 수령",
    "due": "2026-11-07"
  }
}
```

| 필드 | 규칙 |
|---|---|
| `event_id` | 동일 발송 건의 고정 식별자. 영문·숫자·`.`·`_`·`-` 1~80자 |
| `note` | 볼트 기준 기존 `.md` 상대 경로. 절대 경로·`..`·심볼릭 링크·`90_Archive` 금지 |
| `dispatched_on` | 확인한 발송·상신·회신일. `YYYY-MM-DD` |
| `recorded_on` | 노트에 기록하는 날짜. `YYYY-MM-DD` |
| `summary` | 날짜를 제외한 확정 현황 문장. 모르는 수신자·번호는 넣지 않는다 |
| `task_line` | 선택한 기존 미완료 항목의 원문 한 줄. `>`·들여쓰기·기한 등도 그대로 복사 |
| `task_text` | 기존 항목이 없을 때 새 완료 항목의 내용. `task_line`과 둘 중 하나만 지정 |
| `follow_up` | 선택. `text`는 후속 할 일, `due`는 명시된 기한이 있을 때만 지정 |
| `task_heading` | 선택. 기본 `## 할 일`. 프로젝트는 `## 주요 일정` 등 실제 제목 지정 |
| `status_heading` | 선택. 기본 `## 현황`. 다른 섹션을 쓰면 실제 제목 지정 |

발송일을 오늘로 해석할 수 있는 사용자 발화이면 오늘 날짜를 `dispatched_on`에 확정한다.
과거 발송일이 모호하면 확인한다. `due`를 생략하면 후속 항목에 마감일을 넣지 않는다.
후속 업무가 없으면 `follow_up` 자체를 생략한다.

## 실행

```bash
# 변경 미리보기: 기본은 dry-run
python3 .claude/skills/knue-gongmun-draft/scripts/record_dispatch.py "<scratch>/dispatch.json" --vault .

# 사용자가 요청한 발송 기록 범위인지 diff 확인 후 적용
python3 .claude/skills/knue-gongmun-draft/scripts/record_dispatch.py "<scratch>/dispatch.json" --vault . --apply
```

- 기존 할 일을 `[x]`로 바꾸고 `✅ 발송일`을 붙인다. 새로운 완료·후속 항목에는 `➕ 기록일`을 붙인다.
- 현황에는 `- {발송일} {summary}`를 추가한다. 기존 callout 안에 추가하며 원문·status·줄바꿈은 유지한다.
- 대상 제목이 없거나 여러 개, 동일한 `task_line`이 대상 섹션에 여러 개, 코드 펜스 안에만 있는 항목, 미완료가 아닌 항목이면 실패한다. 임의 선택하지 말고 원문을 확인한다.
- 미리보기는 diff만 출력한다. 적용 직전 원본 해시를 다시 확인하고 임시 파일을 원자적으로 교체한다. 변경 충돌은 원본을 덮어쓰지 않고 실패한다.
- 적용 시 현황에 `dispatch-record` 숨김 표식을 남긴다. 같은 ID·같은 내용 재실행은 `UNCHANGED`; 같은 ID·다른 내용은 실패한다. 표식을 지워 재실행하지 않는다. 정정 요청은 기존 기록을 확인해 별도로 처리한다.
- `status`와 최종 발신 본문은 수정하지 않는다. 최종 본문 저장을 요청받았으면 Step 6-4에 따라 별도 반영한다.
- exit 0은 dry-run·적용·동일 이벤트 무변경, exit 1은 입력·대상·충돌 오류, exit 2는 CLI 인자 오류다.

## 검증

```bash
python3 .claude/lib/run_tests.py .claude/skills/knue-gongmun-draft/tests
```

테스트는 임시 노트에서 dry-run·적용·재실행, 이벤트 충돌, 날짜·대상 경계, callout·코드 펜스, 줄바꿈 보존과 변경 충돌을 확인한다.
