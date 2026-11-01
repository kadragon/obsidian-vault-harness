# 완료 원본 자동 삭제 계약

`cleanup_completed.py`는 처리한 `01_Inbox/` 원본을 검증 후 실제 삭제한다. 기본은 dry-run이고 `--apply`가 있어야 `unlink`한다. 삭제 대상 선정과 품질 판정은 메인 스레드가 책임지고, 스크립트는 파일·사본·링크·해시를 검증한다.

## Manifest v1

manifest는 Inbox 밖 scratch에 UTF-8 JSON으로 저장한다. 경로는 볼트 상대경로 또는 볼트 내부 절대경로다. `scope`는 이번에 사용자가 처리를 요청한 파일·폴더의 현재 경로만 적는다. triage로 옮겼으면 옮긴 경로를 사용하고, 지정하지 않은 Inbox 영역을 추가하지 않는다.

```json
{
  "version": 1,
  "scope": ["01_Inbox/action/업무묶음", "01_Inbox/reference/자료.pdf"],
  "files": [
    {
      "source": "01_Inbox/action/업무묶음/공문.pdf",
      "note": "10_Areas/학적/202611_업무/_202611_업무.md",
      "durable": "10_Areas/학적/202611_업무/공문.pdf",
      "branch": "action",
      "completed": true,
      "quality": "PASS",
      "hold": false,
      "source_sha256": "<처리한 원문 SHA-256 64자리 소문자 hex>",
      "note_sha256": "<품질 게이트를 통과한 최종 노트 SHA-256>"
    }
  ]
}
```

`files`에는 scope 안의 실제 파일을 파일별로 등록한다. 폴더 한 줄로 파일을 대신하지 않는다. 필드 의미:

| 필드 | 계약 |
|---|---|
| `source` | 현재 Inbox 원본 파일. scope 내부이고 심볼릭 링크가 아니어야 한다 |
| `note` | action은 `10_Areas/` 업무 노트, reference는 `_Sources/` source note. `.md`이고 `_Assets/`가 아니어야 한다 |
| `durable` | `_Sources/_Assets/` 또는 `10_Areas/`의 영속 사본. source·note와 다른 실제 파일이어야 한다 |
| `branch` | `action` 또는 `reference` |
| `completed` | 이번 원본 처리·노트 반영이 완료됐을 때만 JSON `true` |
| `quality` | 해당 갈래의 필수 검증이 전부 통과했을 때만 문자열 `PASS`. 그 외 `FAIL` 또는 `UNVERIFIED` |
| `hold` | 열린 질문·평가자 보류·사용자 보존 요청이 하나라도 남으면 JSON `true`. 보류가 없을 때만 `false` |
| `source_sha256` | 실제 읽고 처리한 원문 바이트의 SHA-256 |
| `note_sha256` | 품질 검증을 마친 최종 노트 바이트의 SHA-256 |

해시는 `hashlib.sha256(Path(path).read_bytes()).hexdigest()`로 구한다. 처리·품질 검증 시점에 확정하고, 삭제 실패를 없애려고 현재 파일 해시로 덮어쓰지 않는다. 파일이 바뀌면 해당 원본 처리 또는 노트 품질 검증부터 다시 수행한다. `PASS`는 스크립트가 내용의 진위를 판정했다는 뜻이 아니다.

워커는 각 원본의 `source`·`note`·`durable`·`branch`·처리한 원문의 해시와 보류 사유를 반환한다. 메인은 완료·품질 게이트 결과를 확정하고 최종 노트 해시를 더해 manifest를 만든다. 경로는 파일명으로 추정하지 않는다.

## text-absorbed 예외

별도 사본 없이 인라인 흡수한 action `.txt`·`.md`만 `durable: "text-absorbed"`를 쓸 수 있다. 파일 없는 인라인 입력은 manifest에 넣지 않는다.

- 원본은 비어 있지 않은 UTF-8 텍스트여야 한다.
- 원문 전체가 노트의 frontmatter 이후 본문에 정확히 포함되어야 한다. 줄바꿈도 일치해야 한다.
- 완료·품질·보류 및 원본·노트 해시 조건은 동일하다.
- 요약·재서술·OCR 결과만 있거나 reference 갈래이면 삭제하지 않는다. 원본을 영속 사본으로 보존하고 일반 사본 검증을 이용한다.

## 실행과 결과

```bash
python3 .claude/skills/inbox-process/scripts/cleanup_completed.py "<scratch>/cleanup.json" --vault .
python3 .claude/skills/inbox-process/scripts/cleanup_completed.py "<scratch>/cleanup.json" --vault . --apply
```

처리 요청을 마칠 때 두 번째 명령까지 수행한다. dry-run에 보류건이 있으면 보류 사유를 남기되 나머지 검증 완료건의 적용을 막지 않는다. 원본을 개별 삭제하므로 일부 삭제 후 실패해도 나머지 미검증 파일은 그대로 남는다.

- exit 0: scope 내 모든 파일이 검증됨 또는 삭제됨.
- exit 1: 미등록·중복 등록·보류·검증 실패·삭제 실패가 있음. `results`에서 `deleted`와 `preserved`를 분리해 보고한다. 범위 밖·누락 경로 등 등록 오류는 `manifest_errors`에 별도로 나오며 해당 항목은 삭제하지 않는다.
- exit 2: manifest 또는 scope가 잘못됨. 파일 삭제를 시작하지 않는다.

scope의 실제 파일과 목록을 대조하며 미등록 파일은 숨김·OS 부산물도 보존한다. Inbox 밖 경로·심볼릭 링크·같은 실제 파일을 사본으로 제시한 경우도 거부한다. 폴더는 개별 파일 삭제 후 비어 있는 경우에만 `rmdir`한다. `01_Inbox/`와 `action/`·`reference/`·`scraps/` 영역 루트는 남긴다.

적용 직전에 원본·노트 해시, 사본, reference 링크를 다시 검사한다. 검사 중 변경도 보류한다. 다중 파일 트랜잭션은 아니므로 같은 대상에 다른 편집·동기화 작업을 병행하지 않는다. 중단 후에는 남은 파일을 다시 스캔해 manifest를 갱신하되 처리 당시 해시를 임의로 교체하지 않는다.
