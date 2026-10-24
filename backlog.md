# Backlog

## Review Backlog

### PR #25 — [REFACTOR] make note-evaluator default to source fact-check table (2026-10-03)

- [ ] [verify] 새 평가자 계약의 실제 호출 1회 관찰 검증(spec Testing Decisions) — 에이전트 정의가 세션 시작 시 로드돼 같은 세션에서는 관찰 불가. 다음 inbox 처리에서 3-b 호출 시 표·`VERDICT`·`HOLD_DELETE` 반환 여부 확인 (source: task-next) — `.claude/agents/note-evaluator.md` *(deferred: live inbox run needed — agent definitions load at session start)*

### Public history scrub — personal data in past commits (2026-10-19)

- [x] [security] (2026-10-23 done — user ran filter-repo + force push via `!`; verified 0 name hits on all branches, all hwpx previews blank, HEAD tree unchanged; `main` 4094a21) Rewrite public repo history to remove real committee/staff names, extension number, real org/project names and hwpx `Preview/` thumbnails (current tree already pseudonymized). Needs explicit user permission (auto-mode blocked `git-filter-repo` install as Git Destructive).
  - Steps: commit current tree → `python3 -m pip install git-filter-repo` → `git filter-repo --replace-text <rules> --blob-callback <blank Preview/PrvText.txt·PrvImage.png in PK blobs>` over all refs → re-add origin → `git push --force-with-lease` `main` and `harness/pdf-classify-and-simui`.
  - Replace rules: 7 committee names (incl. spaced forms) → 홍길동·박문수·이몽룡·성춘향·임꺽정·장길산·전우치; staff name + extension number → `홍길동`·`1234`; 2 orgs → 가상교육청·다라대학교; 3 sample project titles → `샘플 …`; harness-log `9차 {name} 통합본` → `9차 외부위원 통합본`.
  - Affected paths: `.claude/skills/gwaeop-simui{,-review}/{tests,scripts,references,assets/forms}/`, `assets/fp-period-form.hwpx`, `.claude/skills/knue-report{,-draft}/references/knue-house-style.md`, `docs/harness-log.md`.
  - After: other clones (Syncthing peer) need `git fetch && git reset --hard origin/main`; GitHub `refs/pull/*` and cached commit views survive force push — file a GitHub Support purge request.
  - Done when: `git log --all -p --text` has 0 hits for the name list and every historical hwpx `Preview/PrvText.txt` is empty.
- [ ] [security] Follow-ups to the history scrub: GitHub Support purge request for `refs/pull/1..34/head` and cached commit views; reset the Syncthing peer clone to `origin/main`; delete the pre-scrub mirror backup (`vault-backup.git` in the 2026-10-23 session scratchpad) once confirmed.

## 레거시 메타데이터 참고 (2026-07-31 실측)

> 참고 — 이 PR과 무관한 선행 백로그가 더 크다. 볼트 477건 전수 스캔 시 `status:` 누락 **220건**(2026-07-31 재측정 — improvement 백필로 57건 해소), incident `change_type` 누락 79건. 태그 보완과는 별도 범위이며 이번 작업에서는 수정하지 않았다.
