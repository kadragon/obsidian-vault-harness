---
name: syncthing-conflict-cleanup
description: |
  Syncthing `.sync-conflict` 파일을 볼트 전체에서 스캔해 동일본은 삭제하고 상이본은 검토 후 처리.
  트리거: 'syncthing 충돌', 'conflict 파일 정리', '.sync-conflict 정리', '동기화 충돌 정리', '충돌 파일', 'sync conflict cleanup', 'conflict 치워줘', 'conflict 몇 개야'.
---

# Syncthing Conflict Cleanup

Syncthing이 충돌을 감지하면 원본 파일 옆에
`{base}.sync-conflict-{YYYYMMDD}-{HHMMSS}-{DEVICEID}.{ext}` 형식의 파일을 생성한다.
이 스킬은 그 파일들을 안전하게 찾아 정리한다.

## 작업 모드

| 모드 | 설명 | 트리거 키워드 | 세부 절차 |
|------|------|-------------|----------|
| **scan** | 볼트 전체에서 conflict 파일 목록 + 상태 분류 | 스캔, 목록, 몇 개, 있어? | `references/mode-scan.md` |
| **purge** | 원본과 SHA-256 일치하는 conflict만 일괄 삭제 | 동일 삭제, 중복 정리, purge | `references/mode-purge.md` |
| **review** | 내용이 다른 conflict를 haiku 분석 후 사용자 선택 처리 | 검토, 비교, review, 다르면 | `references/mode-review.md` |
| **(전체)** | scan → purge → review 순차 실행 | 전체 정리, 다 치워줘, 깔끔하게 | 세 references 순차 |

모드를 명시하지 않으면 **전체 시퀀스**(scan → purge → review)를 제안한다.

## 실행 흐름

1. 사용자 요청에서 모드를 확정한다 (명시 없으면 전체 시퀀스 제안).
2. 해당 모드의 references 파일을 Read로 읽어 절차를 따른다. (스크립트가 볼트 루트를 자동 탐지하므로 `cd` 불필요 — 어느 cwd/OS에서도 동작.)
3. 결과를 「보고 형식」으로 요약한다.

## 결정론적 헬퍼 스크립트

스캔·해시 비교·삭제·교체는 `scripts/conflict_cleanup.py`에 위임한다.
LLM이 직접 파일을 순회하거나 조작하는 대신 스크립트 호출을 우선한다.
**기본은 dry-run이며 실제 변경은 `--apply` 명시 시에만 실행된다.**

```bash
# 스캔
python3 .claude/skills/syncthing-conflict-cleanup/scripts/conflict_cleanup.py scan --json

# 동일 conflict 삭제 (dry-run)
python3 .claude/skills/syncthing-conflict-cleanup/scripts/conflict_cleanup.py purge

# 동일 conflict 실제 삭제
python3 .claude/skills/syncthing-conflict-cleanup/scripts/conflict_cleanup.py purge --apply

# 특정 conflict 삭제 (원본 유지)
python3 .claude/skills/syncthing-conflict-cleanup/scripts/conflict_cleanup.py delete "<conflict-path>" --apply

# conflict로 원본 교체
python3 .claude/skills/syncthing-conflict-cleanup/scripts/conflict_cleanup.py replace "<conflict-path>" --apply
```

## 안전 규칙

1. **삭제·교체는 사용자 승인 없이 절대 실행하지 않는다.** purge도 dry-run 먼저. 모든 삭제는 hard delete가 아니라 `<볼트>/.trash/<타임스탬프>/`로 이동(복구 가능); 사용자가 확인 후 `.trash`를 직접 비운다.
2. 작업 대상은 파일명에 `.sync-conflict-` 토큰을 포함한 파일로만 한정한다.
   원본 파일은 `replace` 시에만 conflict로 교체되며, 그 외엔 건드리지 않는다.
3. `90_Archive/` 내부 conflict는 스캔엔 포함되지만 처리는 사용자 명시 동의 필요.
4. 임시 스크립트를 작성한 경우 작업 후 삭제한다.

## 보고 형식

```markdown
## Conflict 정리 결과

| 항목 | 수치 |
|------|------|
| 발견된 conflict | N |
| identical (자동 삭제 대상) | M |
| different (검토 필요) | K |
| orphan (원본 없음) | J |
| 처리 완료 | X |
```

## References

- **`references/mode-scan.md`** — 스캔 절차 및 결과 표 형식
- **`references/mode-purge.md`** — identical conflict 일괄 삭제 절차
- **`references/mode-review.md`** — haiku 위임 분석 + 사용자 선택 처리 절차
- **`scripts/conflict_cleanup.py`** — 결정론적 scan/purge/replace/delete helper
