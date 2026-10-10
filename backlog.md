# Backlog

## Review Backlog

### PR #25 — [REFACTOR] make note-evaluator default to source fact-check table (2026-10-03)

- [ ] [verify] 새 평가자 계약의 실제 호출 1회 관찰 검증(spec Testing Decisions) — 에이전트 정의가 세션 시작 시 로드돼 같은 세션에서는 관찰 불가. 다음 inbox 처리에서 3-b 호출 시 표·`VERDICT`·`HOLD_DELETE` 반환 여부 확인 (source: task-next) — `.claude/agents/note-evaluator.md` *(deferred: live inbox run needed — agent definitions load at session start)*

## 레거시 백필 (PR #18 리뷰에서 실측, 2026-07-30)

새 훅 검사들은 `Write|Edit` 양쪽에 발동하므로, 아래 구형 노트를 편집할 때마다 경고가 재출력된다. 경고 자체는 정확하지만 GP#1상 일괄 수정은 사용자 승인이 필요하다.

- [ ] `10_Areas/` `type: work` **13/201건**에 `#업무/` 태그 없음 → Check 5로 이제 검출됨. area 배정 판단이 필요해 `tag-validator` 경유 권장
- [ ] `10_Areas/` `type: work` **5건**에 필수 앵커(`## 관련`/`## 할 일`) 없음 → PR #21의 과업심의 서식 제외 후 남은 잔여분이며, 전부 진짜 구형 분석 노트다(과업심의 폴더 밖). 목록은 `강사료퇴직금`·`개발공통` 각 1건, `수업성적` 3건. 회차마다 재발하지 않으므로 급하지 않지만 편집 시마다 경고가 뜬다

## 레거시 백필 (PR #20 리뷰에서 실측, 2026-08-02)

Check 5가 `14_Changes/`로 확장되면서 새로 검출되는 분량. 템플릿이 `- #업무/`를 요구하므로 경고 자체는 정확하지만, GP#1상 일괄 수정은 사용자 승인이 필요하다.

- [ ] `14_Changes/` **24/203건**에 구체 `#업무/` 태그 없음 → area 배정 판단이 필요해 `tag-validator` 경유 권장

> 참고 — 이 PR과 무관한 선행 백로그가 더 크다. 볼트 477건 전수 스캔 시 `status:` 누락 **220건**(2026-07-31 재측정 — improvement 백필로 57건 해소), incident `change_type` 누락 79건. 전부 이번 변경 이전부터 있던 것으로, 위 항목과 함께 일괄 처리 여부를 결정하는 편이 낫다.

### PR #29 — [REFACTOR] clarify skill boundaries and standardize canonical names (2026-10-10)

- [ ] [debt] Restrict permanent `weekly_exclude: true` suggestions to one-time processing; unfinished development must remain eligible after completion, via temporary exclusion or an explicit unflagging procedure (source: codex, P2; introduced here) — `.claude/skills/change-log-compile/SKILL.md:72-73`
