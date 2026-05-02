---
name: status-sync
description: "This skill should be used when the user asks to sync or clean up note statuses — 완료된 업무 정리, status 동기화, open 상태 노트 정리, 진행중인데 끝난 거, 업무사안/개선 상태 확인/닫기. Scans 10_Areas/ and 14_Changes/ for notes whose tasks are all done but frontmatter still has `status: open`, then updates them to `status: closed`. Uses checkbox counts and result-section content as signals; delegates ambiguous cases to a status-judge sub-agent. Requires user approval before applying any changes."
---

# Status Sync

`10_Areas/` 업무노트와 `14_Changes/` improvement·incident 노트의 프론트매터
`status` 필드와 실제 작업 상태를 맞춘다. **기존 노트를 수정**하므로 (AGENTS.md
Golden Principle #1의 예외) 적용 전 반드시 사용자 승인을 받는다.

## 대상과 판정 기준

대상: 아래 두 폴더에서 프론트매터에 `status: open`이 있는 `.md` 노트.

| 폴더 | 할 일 섹션 | 맥락 섹션 | 결과 섹션 |
|------|-----------|----------|----------|
| `10_Areas/` | `## 할 일` | `## 현황` | `## 처리 결과` |
| `14_Changes/` | `## 🏷 Todo` | `## 📡 수정 사유` | `## 🛠 주요 코드` |

두 폴더 모두 아래 신호로 판정한다:
- **체크박스**: 할 일 섹션의 `- [ ]`와 `- [x]` 개수를 센다.
- **결과 섹션**: placeholder(`-`) 및 빈 코드 펜스를 제외하고 내용이 있는지 확인한다.
  14_Changes에서는 `## 🛠 주요 코드` fenced block이 채워져 있으면 "작업 완료" 신호로 취급한다.

`scripts/scan.py`로 후보를 3개 버킷으로 분류한다:

| 버킷 | 조건 | 처리 |
|------|------|------|
| `auto_close` | `[ ]` 0개 AND `[x]` ≥1 AND 결과 섹션 채움 | 승인 후 일괄 `closed` |
| `review` | `[ ]` 0개지만 결과 비었거나, 결과는 있는데 체크박스 없음 | `status-judge` 판정 |
| `keep_open` | `[ ]` 남아 있음 또는 신호 부족(할 일·결과 모두 빔) | 유지(보고만) |

결과가 비어 있어도 체크박스가 모두 `[x]`면 "완료됐지만 기록 누락"으로 취급하여
자동 닫기 대신 review 버킷으로 돌린다.

## 실행 흐름

1. **스캔**: 볼트 루트에서 `python3 .claude/skills/status-sync/scripts/scan.py`.
   기본 출력은 compact JSON(`auto_close` 경로, `review` 경로+result_filled,
   `keep_open_count`, `review_bundle` 경로). 전체가 필요하면 `--full`.
   scan.py는 `10_Areas/`와 `14_Changes/`를 모두 훑고, 폴더별 프로파일(할 일·
   맥락·결과 섹션 헤딩)을 내부에서 처리한다.

2. **판정(review 버킷)**: `status-judge` 서브에이전트를 **단 한 번** 호출하고
   `review_bundle` 경로만 넘긴다. review가 비면 건너뛴다. 반환은 TSV N줄
   (`<path>\tCLOSE\t근거` 또는 `<path>\tKEEP\t근거\tTODO`).
   번들 각 줄에는 `profile`("areas" 또는 "changes") 필드가 포함되어 있어
   판정 시 맥락 섹션이 어떤 의미인지 구분할 수 있다.

3. **사용자 보고·승인**:

   ```
   ## status-sync 결과

   ### 닫기 후보 (auto_close + judge:CLOSE)
   - [ ] <경로>  — 근거: …

   ### 체크박스 추가 권장 (judge:KEEP)
   - <경로>  — 추가할 항목: `- [ ] <TODO>`

   ### 유지 (keep_open)
   - <경로>  — 남은 할 일 N개
   ```

4. **적용**(모두 `scripts/apply.py` — 메인 에이전트는 본문을 Read하지 않는다):
   - **닫기**: `apply.py close <path> ...` — 프론트매터 `status: closed`,
     `date modified` 갱신. 폴더 구분 없이 동작.
   - **체크박스 추가**: `apply.py add-todo <path> "<TODO 문구>"` — 할 일 섹션
     끝에 `- [ ] <TODO> ➕ YYYY-MM-DD 📅 YYYY-MM-DD` (두 날짜 모두 오늘)을
     삽입. 10_Areas의 `## 할 일`과 14_Changes의 `## 🏷 Todo` 모두 대상.

## Wiki 피드백 (적용 후)

`apply.py close` 적용이 완료된 후, 종결된 노트 목록을 `_Wiki/contracts.md` Wiki Feedback Payload 규칙에 따라 obsidian-operator에 위임한다.

- **log.md append** (종결 건 일괄): 각 노트에 대해 `- {오늘날짜} #closed [[{노트 경로}]] — {도메인} 종결`
- **범위 제한**: log.md 만 갱신한다. MOC 갱신은 status-sync 범위 밖이며, 각 노트를 처음 생성한 skill(incident-analyze·improvement-plan)의 Step 5(Wiki 피드백)가 담당한다.
- **도메인 식별**: `apply.py`가 반환하는 닫힌 노트 경로에서 frontmatter `tags` 또는 파일명으로 추정. 식별 불가 시 "unknown"으로 기록.
- **실패 허용**: obsidian-operator 위임 실패 시 status-sync 적용 자체를 롤백하지 않는다. log.md 미갱신 사실만 보고한다.

## 참고

설계 배경(토큰 절감 전략, 폴더 프로파일 확장 방법) → `references/design.md`
