# Mode: Scan

볼트 전체에서 conflict 파일을 탐색하고 상태별로 분류하여 보고한다.

## Step 1 — 스크립트 실행

스크립트는 자신의 위치에서 볼트 루트를 자동 탐지한다 (cwd 무관, OS 무관).

```bash
python3 .claude/skills/syncthing-conflict-cleanup/scripts/conflict_cleanup.py scan --json
```

## Step 2 — 결과 파싱 및 분류

JSON 출력에서 각 항목의 `status` 필드를 기준으로 분류한다:

| status | 의미 |
|--------|------|
| `identical` | 원본과 SHA-256 일치 → purge 대상 |
| `different` | 내용 차이 있음 → review 대상 |
| `orphan` | 원본이 존재하지 않음 → 별도 처리 필요 |
| `non-text` | `.md`가 아닌 파일 → diff 불가, 크기/날짜만 제공 |

## Step 3 — 결과 보고

스캔 결과를 다음 형식으로 사용자에게 보고한다:

```markdown
## Conflict 스캔 결과

| 상태 | 수 | 설명 |
|------|----|------|
| identical | N | 원본과 동일 — purge로 즉시 정리 가능 |
| different | M | 내용 차이 있음 — review 필요 |
| orphan | K | 원본 없음 — 별도 결정 필요 |
| non-text | J | 바이너리/비-md — 수동 확인 |
| **합계** | **T** | |
```

이어서 모드 추천:
- identical > 0 → "purge 모드로 동일 항목을 먼저 정리하시겠습니까?"
- different > 0 → "review 모드로 차이 항목을 검토하시겠습니까?"
- 전체 정리 시퀀스 중이라면 다음 모드로 자동 진행.

## 주의

- `90_Archive/` 내부 항목은 결과에 포함되지만 결과 표에 경로와 함께
  "(archive)" 표시를 달아 구분한다.
- 스캔 자체는 읽기 전용이므로 사용자 승인 없이 실행해도 무방하다.
