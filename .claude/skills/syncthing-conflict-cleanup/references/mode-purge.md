# Mode: Purge

원본과 SHA-256이 완전히 동일한 conflict 파일만 `<볼트>/.trash/`로 이동한다 (복구 가능 — hard delete 아님).
원본은 절대 건드리지 않는다. `.trash`는 스캔에서 제외되며 사용자가 확인 후 직접 비운다.

## Step 1 — 대상 확인 (dry-run)

```bash
python3 .claude/skills/syncthing-conflict-cleanup/scripts/conflict_cleanup.py purge
```

출력 예시:
```
[DRY-RUN] 휴지통 이동 예정:
  10_Areas/기타/202603_.../파일.sync-conflict-20260427-065342-YTJXM34.md  (원본과 동일)
  10_Areas/기타/202603_.../파일.sync-conflict-20260427-065344-WERFXNH.md  (원본과 동일)

총 2개 파일이 .trash로 이동될 예정입니다. (원본 파일은 변경되지 않습니다.)
실제 실행하려면 --apply 옵션을 추가하세요.
```

## Step 2 — 사용자 승인

dry-run 결과를 사용자에게 보여주고 승인을 구한다:

> "위 N개의 conflict 파일은 원본과 완전히 동일하여 안전하게 정리할 수 있습니다.
> `.trash`로 이동할까요? (hard delete 아님 — 복구 가능)"

대상이 없으면 ("identical 항목 0개") 사용자에게 알리고 모드를 종료한다.

## Step 3 — 실제 실행 (.trash 이동)

사용자가 승인하면:

```bash
python3 .claude/skills/syncthing-conflict-cleanup/scripts/conflict_cleanup.py purge --apply
```

## Step 4 — 결과 보고

```markdown
## Purge 결과

| 항목 | 수치 |
|------|------|
| 대상 | N |
| .trash 이동 | N |
| 원본 파일 변경 | 0 |
```

전체 시퀀스 중이라면 이어서 review 모드를 제안한다.

## 주의

- `status: different`, `orphan`, `non-text` 항목은 purge 대상에서 제외된다.
  스크립트가 이를 자동으로 필터링한다.
- purge 이후에도 `different` 항목이 남아 있으면 반드시 review 모드를 이어서
  안내한다.
