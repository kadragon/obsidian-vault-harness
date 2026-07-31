# Tasks

Out-of-scope findings routed here from review cycles. Items touching existing notes need user approval first (AGENTS.md Golden Principle #1 — 기존 노트 불변).

## 레거시 백필 (PR #18 리뷰에서 실측, 2026-07-30)

새 훅 검사들은 `Write|Edit` 양쪽에 발동하므로, 아래 구형 노트를 편집할 때마다 경고가 재출력된다. 경고 자체는 정확하지만 GP#1상 일괄 수정은 사용자 승인이 필요하다.

- [ ] `14_Changes/improvement/` **57/97건**에 `change_type: improvement` 누락 → Check 3 확장으로 이제 검출됨. frontmatter 1줄 추가로 해소되는 기계적 작업. 승인 시 스크립트 일괄 처리 가능
- [ ] `10_Areas/` `type: work` **20/200건**이 필수 앵커(`## 관련`/`## 할 일`) 미보유 → 전부 구형 분석 노트. 구조 변경이라 건별 판단 필요, 일괄 처리 부적합
- [ ] `10_Areas/` `type: work` **13/201건**에 `#업무/` 태그 없음 → Check 5로 이제 검출됨. area 배정 판단이 필요해 `tag-validator` 경유 권장
- [ ] `10_Areas/` `type: work` **56/201건**에 `#부서/` 태그 없음 → 관행이 아니어서(28%) 기계화하지 않음. 규칙 자체를 유지할지(→ 백필) 선택 필드로 강등할지 **결정 필요**

> 참고 — 이 PR과 무관한 선행 백로그가 더 크다. 볼트 477건 전수 스캔 시 `status:` 누락 277건, incident `change_type` 누락 79건. 전부 이번 변경 이전부터 있던 것으로, 위 항목과 함께 일괄 처리 여부를 결정하는 편이 낫다.
