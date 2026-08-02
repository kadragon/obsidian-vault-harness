# Tasks

Out-of-scope findings routed here from review cycles. Items touching existing notes need user approval first (AGENTS.md Golden Principle #1 — 기존 노트 불변).

## 레거시 백필 (PR #18 리뷰에서 실측, 2026-07-30)

새 훅 검사들은 `Write|Edit` 양쪽에 발동하므로, 아래 구형 노트를 편집할 때마다 경고가 재출력된다. 경고 자체는 정확하지만 GP#1상 일괄 수정은 사용자 승인이 필요하다.

- [ ] `10_Areas/` `type: work` **13/201건**에 `#업무/` 태그 없음 → Check 5로 이제 검출됨. area 배정 판단이 필요해 `tag-validator` 경유 권장

## 레거시 백필 (PR #20 리뷰에서 실측, 2026-08-02)

Check 5가 `14_Changes/`로 확장되면서 새로 검출되는 분량. 템플릿이 `- #업무/`를 요구하므로 경고 자체는 정확하지만, GP#1상 일괄 수정은 사용자 승인이 필요하다.

- [ ] `14_Changes/` **24/203건**에 구체 `#업무/` 태그 없음 → area 배정 판단이 필요해 `tag-validator` 경유 권장

## 과업심의 잔여 경고 (2026-08-02 실측)

Check 4 경로 제외로 앵커 오탐은 끊겼으나(20 → 5건), 나머지 두 검사는 회차마다 계속 발동한다. 실측 `10_Areas/과업심의/` `type: work` 18건 중:

- [ ] **status 누락 10건** → Check 2b가 회차마다 경고. 심의 서식에 `status:` 를 요구할지, 서식을 `type: work` 밖으로 옮길지 **결정 필요**
- [ ] **`#업무/` 미보유 10건** → Check 5가 회차마다 경고. 심의 서식에 `#업무/과업심의`를 부여할지, Check 5에서도 경로를 제외할지 **결정 필요**

> 참고 — 이 PR과 무관한 선행 백로그가 더 크다. 볼트 477건 전수 스캔 시 `status:` 누락 **220건**(2026-07-31 재측정 — improvement 백필로 57건 해소), incident `change_type` 누락 79건. 전부 이번 변경 이전부터 있던 것으로, 위 항목과 함께 일괄 처리 여부를 결정하는 편이 낫다.
