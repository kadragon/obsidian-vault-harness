# 하네스 변경 기록

`dev:harness-curate` 루프가 만든 편집의 변경 이력. 각 행은 **떨어질 수 있는 예측**을 달고,
다음 회차 재감사(Step 2.5)가 그 예측을 판정해 `Verified` 열을 채운다.
`Verified`가 `pending`·`unverified`이거나 해결 메모 없는 `failed`면 다음 회차에 다시 올라온다.

| Date | Change | Predicted impact | Verified |
|------|--------|------------------|----------|
| 2026-09-05 | 스킬 문서 장황함 정비 — `check-skill-doc.py` PostToolUse 훅 신설(길이·근거 서사 토큰·굵게 밀도·깨진 스니펫), `inbox-process` 819→614줄(PDF 절차를 `references/pdf-reading.md` 단일 출처로, 워커 규약·선례 규칙 중복 제거, 근거 서사는 아래 §규칙 근거로 이관), gwaeop 참고 4종 표·본문 굵게 245쌍 제거, Chrome 경로 하드코딩 → `render_pdf.py`(OS 자동 탐색), 머신 종속 서술(poppler·Tesseract·Windows) 제거, 깨진 `"\n"` 스니펫 2건·태그 힌트 예시(`#업무/학사/…`)·요일 오기 수정 | `--sweep` 0건이 유지된다. 다음 회차 스킬 편집에서 훅 경고를 받고도 근거 서사를 SKILL.md에 남긴 커밋이 0건. inbox-process 워커가 `pdf-reading.md`를 Read하는 호출이 트랜스크립트에 나타난다 | pending |
| 2026-09-01 | `gwaeop-simui` — 전달본에서 §4 권고 사항 절 제거(L4는 노트 전용), B 항목 채택 기준·묶기 규칙 추가, 추정가격 2천만원 미만 시 경쟁입찰 전제 지적 금지 게이트 추가. `report.html`·`lint_findings.py` 동반 수정 | 다음 회차 보완요청 PDF에서 사용자의 "항목 삭제해서 다시 만들어줘" 요청이 0건이 된다. 특히 권고사항 절 삭제 요청과 B-N 다건 삭제가 사라진다 | pending |
| 2026-09-01 | `gongmun-draft` — 스코프를 개선 결과 안내 공문에서 대외 발신 문서 전반으로 확장, B 유형(회신·안내) 절차 추가, 트리거에 "회신 문구 초안"·"메일 초안 작성" 등 추가 | 회신·메일 초안 요청 시 스킬이 발화한다. 다음 회차 `SKILLS-ACTIVE`에서 `gongmun-draft` ≥1 | pending |
| 2026-09-01 | `deliverable-review` 신규 스킬 — 납품 산출물 검수 5축 대조 + 보완요구 메일 초안 + 재제출본 회차 대조. `AGENTS.md`·`docs/delegation.md`·`docs/runbook.md`에 등록 | 다음 산출물 검토 요청("결과물 받았는데 검토해줄수 있어?")에서 발화한다. 검토 노트에 `보완요구` 열과 `실물 확인 항목` 절이 사람 손 없이 나온다 | pending |
| 2026-09-01 | `check-nested-delegation.py` — 에이전트 이름 알파벳을 글롭 단독에서 글롭 ∪ 폴백 합집합으로 변경 | 에이전트 `.md`를 지워도 그 이름을 가리키는 산문 위임 지시가 계속 탐지된다. `_agent_names()`가 항상 `_FALLBACK_AGENT_NAMES`를 포함 — 인라인 assert로 확인 완료 | 2026-09-01 — 검증 스크립트 통과(폴백 10종 전부 포함) |
| 2026-09-01 | `AGENTS.md` — 글로벌 지침과 중복된 하드스톱·Maintenance 기준 제거, 컨텍스트 리셋 규칙을 "의도적 override"로 명시 | 같은 규칙이 두 계층에 남아 생기는 재발화가 없다. 다음 회차 Signal 7에서 이 3쌍이 `DISMISSED`로 억제된다 | pending |
| 2026-09-01 | 메모리 `googledrive-knue-folder` → `docs/migration-googledrive.md` 승격 + Docs Index 등록, 메모리 파일 삭제 | Codex 세션에서도 GoogleDrive 이관 상태를 조회할 수 있다. `AGENTS.md` Docs Index에서 도달 가능 | 2026-09-01 — 파일 생성·인덱스 등록·메모리 삭제 확인 |
| 2026-09-01 | `claude-md-management` 플러그인 프로젝트 스코프 비활성 | 이 레포에서 해당 플러그인 스킬 발화 0건 유지. 지침 파일은 `dev:harness-*`가 단독 관리 | pending |

## 판정 보류 — 삭제하지 않기로 한 것

| Date | 후보 | 판정 | 근거 |
|------|------|------|------|
| 2026-09-01 | `vault-navigator` 에이전트 | **KEEP** | 호출 0회는 사문이 아니라 설계된 결과. `inbox-process/SKILL.md:127`의 67k 토큰 비용 게이트 뒤에서만 호출되고(`SKILL.md:16,132-133,183`), MOC 공백 분기에서는 필수. 트랜스크립트 스캐너는 오케스트레이터 경유 호출을 과소 계수한다 |
| 2026-09-01 | `obsidian-operator` 에이전트 | **KEEP** | `obsidian` CLI를 구동하는 유일한 자산. `docs/migration-flat-areas.md:51` — 앱이 열린 상태로 이동해야 링크가 자동 갱신되므로 `Bash mv`로 대체 불가 |
| 2026-09-01 | `training-note-manager` 에이전트 | **KEEP** | `20_Training/`은 `docs/eval-criteria.md:113`·`note_rules.py:208-210`이 기계 검사에서 명시적으로 제외한 영역이고, 이 에이전트가 유일한 커버리지. 삭제 시 `.claude/agents/workflows/training-manage/**`가 고아가 된다 |

## 규칙 근거 — 스킬 문서에서 이관 (2026-09-05)

스킬 문서의 규칙은 명령형만 남기고, 그 규칙을 낳은 측정·사고는 여기에 둔다. 규칙을 바꾸거나 지울 때 이 표를 먼저 본다.

| 규칙 (위치) | 근거 |
|------|------|
| 선례 조사는 MOC 우선, `vault-navigator`는 폴백 (`inbox-process/SKILL.md` 3단계) | navigator 1회 약 67k 토큰, MOC 1건 Read 약 5k (2026-07-30). 회차성 반복 공문은 MOC가 선례·담당자·주기를 이미 담고 있어 대부분 중복 지출 |
| 워커에 선례 최대 1건, 용도는 사실 참조만·구조 승계 금지 (`dispatch-guide.md`) | 2026-07-30 "선례 섹션 구조를 승계하라" 지시로 note-evaluator FAIL → 노트 재작성 발생. 2건 이상 Read시키면 구조 판단이 흔들림 |
| `note-evaluator`는 조건부 호출 (`SKILL.md` 5단계 3-b) | 1회 약 100k 토큰. 훅이 검사한 범위를 LLM으로 재실행하는 낭비 (2026-07-30, `docs/enforcement.md` 승격 로그 #13) |
| `#부서/`는 선택 필드 — 부재를 지적하지 않음 | 2026-08-02 강등. 기존 노트 28%가 미보유 |
| 제목에 날짜 프리픽스 금지, 날짜는 `doc_date` (`action-branch.md` §5) | 2026-07-30 폐기. 종전 규칙 준수율 32%, 작성일이라 업무 발생 시점을 못 담음 |
| PDF는 분류기 결과로 바로 분기, Read로 "텍스트 안 나옴" 확인 절차 없음 (`pdf-reading.md`) | 볼트 PDF 545건 대조에서 분류기와 실제 텍스트 수확량 완전 일치 (`scanned` 146건 0자/쪽, `text_based` 380건 중 50자 미만 0건) |
| PDF 본문은 PyMuPDF로 읽는다 — Read 도구를 쓰지 않음 | Read 도구의 PDF 지원은 poppler 유무에 좌우된다(Windows 머신 미설치, macOS 설치). 머신마다 갈리는 사실을 문서에 박지 않고 항상 동작하는 경로 하나만 남김 |
| OCR 실패 시 건너뛰고 열린 질문 (`pdf-reading.md` §3) | Tesseract는 파이썬 패키지가 아니라 `uv`가 못 준다. 2026-08-04 Windows 머신에서 실패 확인. 실패는 `ERROR: OCR failed`로 크게 드러남 |
| Handysoft 추출본 경로는 해시 기반 (`extract_handysoft_pdf.py`) | 원본 전체 바이트 md5 앞 8자 — 서로 다른 문서가 같은 경로를 쓰는 일이 없고, triage와 워커가 같은 파일을 두 번 분류해도 재사용됨 |
| 공문번호 `--doc-number`에 날짜를 붙이지 않음 (`action-branch.md`) | `find_duplicates()`가 substring 매칭이라 날짜가 붙으면 과거 날짜 없는 노트와 매칭되지 않아 중복을 놓침 |
| 전달본에 권고 사항 절 없음, L4는 노트 전용 (`gwaeop-simui/output-format.md` §2-2) | 4회차 연속 사용자가 발행 직전 권고 절을 통째로 삭제. 근거 없는 항목이 강한 지적의 강제력까지 희석 |
| 지침 고시번호·시행일은 원문에서 확인 (`legal-basis.md` 상단) | 2026-08-18 검색엔진 요약이 2023-05-15 개정을 2025-03-25로 잘못 표기한 사례 |
| 전달본에 미보완·미회신 시 불이익 고지 문장 없음 (`gwaeop-simui/output-format.md` §2-3) | 2026-09-08 사용자 상시 방침 확정. "기한 내 회신이 없으면 원본 그대로 위원에게 송부"·"미보완 시 지적사항이 그대로 위원에게 전달됨" 두 문장을 발행 직전 삭제 요청 — 같은 기관 내 발주부서 대상 실무 협조 문서이지 통보문이 아니며, 강제력은 지적의 근거 조문과 기한의 근거에서 나옴. 미회신 시 실제 처리는 간사 몫이므로 노트에만 (SKILL.md Step 6-5) |
