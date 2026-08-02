> **Agent workflow — not a skill.** `training-note-manager` 에이전트가 교육 노트 평가·표준화 시 Read로 읽는 절차서다.
> Skill 툴로 호출되지 않는다. 소유 에이전트: `.claude/agents/training-note-manager.md`

# Training Note Management

교육/연수 노트를 평가하고 표준화하는 절차.

템플릿 구조 전체: `99_Template/_교육.md` 참조.

## 모드 선택

| 요청 유형 | 모드 |
|----------|------|
| 기존 노트 품질 평가 | Mode 1: assess |
| 기존 노트 템플릿 적용 | Mode 2: standardize |
| 새 교육 기록 작성 | Mode 3: create |
| 20_Training 전체 정리 | Mode 4: sweep |

---

## Mode 1: 품질 평가 (assess)

기존 교육 노트의 품질을 평가하여 정리 방향을 제시한다.

1. `find 20_Training/{target}/ -name "*.md" -type f` 로 파일 수집
2. 각 노트를 읽고 내용 충실도·실무 가치·완성도(각 1-5점) 기준으로 평가
3. 평균 점수로 KEEP / KEEP(보완) / MERGE / DELETE 분류
4. 평가 보고서를 사용자에게 제시하고 확인 후 다음 단계 진행

상세 채점 기준 및 보고서 포맷 → `references/mode-assess.md`

---

## Mode 2: 표준화 (standardize)

기존 노트를 표준 템플릿 구조(`99_Template/_교육.md`)로 재배치한다.

1. Read로 전체 내용 읽기 (2000줄+ 파일은 분할 읽기)
2. 본문에서 교육명·강사·일시·장소·목표 추출
3. Frontmatter 정비 → H1 확인 → 교육 정보 섹션 구성 → 본문 재배치 → 핵심 정리 생성 → 참고자료·할 일 이동
4. Write 도구로 전체 파일을 한 번에 덮어쓰기

상세 추출 소스 및 재배치 규칙 7단계 → `references/mode-standardize.md`

---

## Mode 3: 신규 작성 (create)

새 교육 기록을 템플릿 기반으로 생성한다.

1. `qmd vsearch "{교육 주제 또는 과정명}" -n 5` 로 유사 노트 확인
   - 동일 과정 회차로 판단되면 기존 폴더 하위에 추가할지 사용자에게 확인
2. 경로 결정: `20_Training/{year}/{교육명}.md` 또는 다회차 과정은 폴더 생성
3. 사용자 제공 정보로 `## 교육 정보` 채우기 — 누락 정보는 hard stop
4. `## 핵심 내용` 하위에 교육 내용 구조화
5. 본문 기반으로 `## 핵심 정리` 3개 항목 작성

---

## Mode 4: 일괄 정리 (sweep)

`20_Training/` 전체를 스캔하여 구조 점검 후 Mode 1 → Mode 2 순차 실행한다.
5건+ 노트가 누적되고 `_Wiki/topics/교육-운영-MOC.md`가 없으면 MOC 생성을 제안한다.

상세 점검 항목 및 MOC 제안 절차 → `references/mode-sweep.md`

---

## 공통 규칙

**DELETE 판단 기준** (단일 출처: `references/mode-assess.md` "DELETE 확정 기준") — 하나라도 해당하면 점수와 무관하게 삭제 후보:
- 본문 3줄 이하 (제목/헤딩만)
- 70% 이상 섹션이 비어있음 (제목만 있고 내용 없음)
- 텍스트 설명 없이 이미지만 나열
- 하위 노트가 존재하는 순수 목차 노트
- 재참고 가치 없는 일반 상식 수준 내용

**파일 배치 규칙**:
- `20_Training/` 루트에 파일 미배치 — 연도 폴더 필수
- 연도 폴더: `20_Training/{year}/`
- 교육과정 폴더: `20_Training/{year}/{교육과정명}/`
- 첨부자료: 같은 폴더 또는 `자료/` 하위
- 완료 교육: `status: closed` 변경 (이동 불필요)

---

## References

- `references/mode-assess.md` — Mode 1 채점 기준, 분류표, 보고서 포맷
- `references/mode-standardize.md` — Mode 2 추출 소스, 재배치 규칙 7단계
- `references/mode-sweep.md` — Mode 4 점검 항목, MOC 제안 절차
