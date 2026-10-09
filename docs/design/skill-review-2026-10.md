# 스킬 전수 리뷰 개선 설계 (2026-10-09)

## Problem Statement

`.claude/skills/`에 13개 디렉토리가 있었으나 실체는 스킬 11개 + Claude Code mod(플러그인) 2건이었다.
`prompt-cache-control`·`tool-timing-badge`는 `SKILL.md` 없이 `hooks/`+`.claude-plugin/` 구조로,
Skill 도구로 디스커버리되지 않으면서 스킬 디렉토리를 점유해 스킬 수 오판과 runbook 배치 규칙
("직접 호출 안 하면 스킬 아님") 위반을 유발했다. 장기간 누적된 11개 스킬에도 구조·트리거·테스트
편차가 커서, 방치하면 오발동·외부 의존 파손·파괴적 동작 무테스트 상태가 남는다.

전수 리뷰(병렬 4그룹) 실측 요약:

1. **오남용 2건** — mod를 스킬 디렉토리에 상주시켜 `xxx@skills-dir` 훅 로드로 동작. 외부 저작자
   (`davila7/claude-code-templates`), 전역 설정(`~/.claude/settings.json`) 의존으로 볼트 재현성 저해.
2. **트리거 충돌** — `change-log` vs `weekly-report`(한 단어 차이), `knue-gongmun` B유형 vs
   `deliverable-review` Step 4(메일 규칙 중복 정의), `knue-report` 트리거 24개로 오발동 1순위,
   `inbox-process`의 범용어("문서 정리해줘") 과다 흡수.
3. **구조 편차** — `deliverable-review/SKILL.md:168` 단일파일 모놀리스(references 0건)가 최악,
   `knue-report/SKILL.md:25`(위임만)는 모범. `gwaeop-simui` references 비대(`legal-basis` 347줄).
4. **테스트 공백** — `change-log`(tests/ 없음), `syncthing-conflict-cleanup`(SHA-256+파괴적 동작인데
   테스트 0, 최위험), `knue-*`·`weekly-report`·`deliverable-review` 테스트 없음.
   `vault-cleanup`·`status-sync`·`project-restructure`는 스크립트+테스트 완비로 모범.
5. **외부·공유 의존** — `knue-*`가 `prod:gongmun-draft`·`prod:report-draft`에 통째 위임(버전·대체 규칙 없음).
   `gwaeop-simui` Step 1과 `inbox-process`가 `ocr_pdf.py` 공유(드리프트 시 양쪽 파손).
   `gwaeop-simui` Step 5-2 "지적 1건당 에이전트 1개"는 상한 없음.
6. **문서 드리프트** — `docs/delegation.md` 라우팅표에 `weekly-report`·`gwaeop-simui` 행 누락
   (AGENTS.md·runbook은 있음). `__pycache__/` 커밋 잔재가 skills 내부에 존재.

## Solution

새 문서 없이 **위반 제거 → 충돌 해소 → 테스트 보강** 순서로 접는다. 원칙: 스킬 디렉토리는
사용자 직접 호출 스킬만, 절차 상술은 references로, 결정론적 로직은 스크립트로.

- **P0 장위 정리 (본 설계에서 수행)** — mod 2건을 `.claude/skills/` 밖으로 제거
  (`.trash/skills-purge-20261009/`로 이동, 영구 삭제는 사용자 확인 후 `rm -rf`).
  `docs/runbook.md` Skills Reference 하단에 "스킬이 아닌 상주 플러그인" 섹션은 후속 작업으로 남김.
- **P1 트리거 경계** — `change-log`에서 "직전주 업무 정리·지난 주 처리한 업무" 삭제(기능 개선 한정어 필수화),
  `weekly-report` description에 "직전주 실적은 change-log 먼저" 우선순위 추가(knue 선례 답습).
  `knue-gongmun` B유형과 `deliverable-review` Step 4 중 메일 톤 규칙은 한쪽(`knue-gongmun` Step 4.5 준용)으로
  단일화. `knue-report` 트리거 24개 → 10개 내로 축소. `inbox-process` 범용 3종에 `01_Inbox` 한정자 추가.
- **P1 구조** — `deliverable-review` Step 2·Step 4를 `references/review-axes.md`·`mail-template.md`로 분리
  (목표 SKILL ≤100줄). `weekly-report` 4단계 형식표 → `references/format-rules.md`.
  `syncthing` mode-review 140줄 → 프롬프트 템플릿 분리. `gwaeop-simui` 절차-외 스크립트 2종 경계 명시.
- **P2 테스트·의존** — `syncthing` 회귀 테스트 신설(identical/different/orphan + dry-run/apply, 최우선),
  `change-log` 제외기준 2종+용어제거 5케이스, `deliverable-review` 판정 규칙 3케이스.
  `prod:*` 의존을 runbook에 버전·설치 경로·부재 시 대체 규칙으로 문서화. 공유 `ocr_pdf.py` 단일 소유 선언.
  `gwaeop-simui` 5-2 병렬검증 상한(예: 5건 초과 시 일괄) 명시. 하드코딩(이메일·예시일자·메뉴코드) 상수 이관.
- **P2 문서** — `docs/delegation.md`에 2행 추가해 AGENTS.md와 일치. `__pycache__/` git 제거 +
  `.gitignore`에 `__pycache__/` 확인.

## Scope

- IN: `.claude/skills/` 11개 스킬 + mod 2건 제거, `docs/delegation.md`·`docs/runbook.md` 동기화,
  테스트 3종 신설.
- OUT: 스킬 병합·신설 없음. `prod:*` 외부 플러그인 자체 수정 없음(의존 문서화만).
  `10_Areas/`·`14_Changes/` 노트 백필 없음(GP#1 승인 필요).

## Testing Decisions

- `syncthing` 테스트는 `conflict_cleanup.py`의 scan/purge/replace/delete 경로를 커버해야 한다
  (파괴적 동작이므로 dry-run 기본 검증 포함).
- `change-log`·`deliverable-review` 테스트는 판정 규칙 회귀 케이스 최소 기준으로 한다.
- 트리거 문구 변경 후에는 다음 실제 호출 1회에서 오발동 여부를 관찰 검증한다(정의 로드 시점상
  같은 세션 관찰 불가 시 deferred로 backlog에 남김).

## Decisions

- [x] mod 2건은 복구 없이 제거한다 — 스킬이 아니며 외부 템플릿 복제본이라 볼트에 둘 이유가 없음
  (필요 시 upstream에서 재설치).
- [ ] 제거물은 `.trash/skills-purge-20261009/`에 보관 중 — 영구 삭제(`rm -rf`) 전 사용자 확인 필요.
- [ ] P1·P2 항목은 승인된 순서대로 별도 작업으로 수행한다 (본 설계는 P0만 실행).
