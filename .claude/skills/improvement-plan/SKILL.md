---
name: improvement-plan
description: "Workflow reference for improvement-planner agent. Do NOT invoke directly — use the improvement-planner agent instead. Contains step-by-step workflow for planning and documenting 통합학사시스템 improvements."
---

# Improvement Planning

통합학사시스템 개선 사항을 계획하고 문서화하는 절차.

## 워크플로우

### Step 1: 요구사항 분석

개선 요청에서 다음을 파악한다:

| 항목 | 파악 내용 |
|------|----------|
| 대상 시스템 | 통합학사, KORUS, 홈페이지, 수강신청 등 |
| 변경 유형 | 쿼리 수정, 프로시저 변경, UI 변경, 신규 기능 |
| 영향 범위 | 단일 메뉴, 복수 메뉴, 시스템 전체 |
| 긴급도 | 즉시, 이번 주, 다음 업데이트 (명시 안 되면 "다음 업데이트" 기본) |
| 요청 출처 | ITSM, 구두 요청, 인시던트 후속 조치 (명시 안 되면 생략) |

실제 코드 파일(XML, 프로시저 등)에 접근 불가한 경우: 변경 전 코드 블록에 `-- 실제 파일 확인 필요`를 주석으로 남기고, 요청에서 파악 가능한 범위까지만 작성한다.

### Step 2: 사전 컨텍스트 및 과거 사례 확인

`_Wiki/syntheses/`·`14_Changes/improvement/`·`90_Archive/`에서 관련 과거 사례와 기존 분석을 검색한다.

검색 방법:
1. `qmd vsearch "{개선 주제 설명}" -n 5` — `_Wiki/syntheses/`에 이미 정리된 유사 분석이 있는지 먼저 확인
2. `qmd search "{프로시저명 또는 키워드}" -n 10` — 관련 개선 사례 탐색
3. Grep으로 프로시저명/메뉴코드 정확 매칭 확인

syntheses 에 기존 분석이 있으면 이후 단계에서 해당 내용을 우선 활용한다.

### Step 3: 개선 노트 생성

#### 경로 + 파일명 (스크립트 위임)

반기 판단과 동명 파일 suffix 결정은 `scripts/new_improvement_path.py`에 위임한다.

```bash
python3 .claude/skills/improvement-plan/scripts/new_improvement_path.py "수강신청 로그 개선"
# → /Users/.../14_Changes/improvement/2026/상반기/수강신청 로그 개선.md
```

스크립트가 하는 일: 작성월 1~6 → `상반기` / 7~12 → `하반기`, 해당 연도(양 반기 모두)에서 동일 파일명이 있으면 `_2`, `_3` 자동 증가. 제목은 내용 기반 자유 형식 한글로 LLM이 결정한다 (예: `메뉴접속수 지연 쿼리 수정`, `수강신청 시스템 로그 개선`).

#### 노트 구조

`99_Template/_개선.md` 템플릿을 기준으로 한다. 각 섹션을 다음과 같이 채운다:

| 섹션 | 채우는 내용 |
|------|-----------|
| frontmatter | `type: change`, `change_type: improvement`, `status: open` (`date created`/`date modified`는 Linter가 자동 관리 -- 직접 넣지 않음). 공문에서 비롯된 개선이면 `doc_date: YYYY-MM-DD`(공문 시행일), 접수일이 다를 때만 `recv_date` 추가 -- `99_Template/_메타데이터 규칙.md` |
| `#` 제목 | 개선 제목 |
| `## 🏷 Todo` | `- [ ] {구체적 작업 항목} 📅 {YYYY-MM-DD} ➕ {오늘 날짜}` |
| `## 📑 메뉴` | `{메뉴코드} / #업무/{영역}/{하위영역}/{메뉴명}` |
| `## 📂 관련 파일` | `{파일명.xml}` 또는 `{프로시저명}` |
| `## 📡 수정 사유` | 왜 이 변경이 필요한지 |
| `## 관련 문서` | **실제 관련 문서(설계 문서, 스펙 문서, 과거 유사 개선 노트 등) 있을 때만 포함**. 없으면 섹션(헤딩+콜아웃) 전체를 생략 — 빈 `[[ ]]` 플레이스홀더 금지 |
| `## 🛠 주요 코드` | 변경 전/후 코드 (code block) |

**주요 코드 작성 시**: 변경 전/후를 `-- 변경 전` / `-- 변경 후` 주석으로 구분한다.

### Step 4: Wiki 피드백

노트 생성 직후 `_Wiki/contracts.md` Wiki Feedback Payload 규칙에 따라 **직접 수행**한다 (Read + Edit). obsidian-operator 위임 금지 — 이 스킬은 서브에이전트(improvement-planner)가 읽으며, **서브에이전트는 다른 서브에이전트를 호출할 수 없다**(도구 목록에 `Agent` 없음). 과거 위임 지시는 실행 불가였다.

1. **log.md append**: `- {오늘날짜} #improvement [[{노트 경로}]] — {도메인} 생성`
2. **MOC 확인**: `_Wiki/topics/{도메인}-운영-MOC.md` 존재 여부 점검
   - 존재 → **양방향**: MOC `## 미완료 업무 목록`/`## 반복 인시던트 패턴`에 wikilink append + 이 노트 `## 관련 문서`에 `- 운영 MOC: [[{도메인}-운영-MOC]]` 역링크 추가 (contracts.md MOC 갱신 조건)
   - 없음 → 동일 도메인 개선 수 `qmd search "{도메인} improvement" --json -n 20`으로 카운트 → 3건+ 이면 "운영 MOC 생성을 권장합니다" 보고

### Step 5: 업무 태그 지정

태그는 **직접 작성**한다. 후보를 정한 뒤 `python3 .claude/lib/validate_tag.py --json -` 로 검증하고, `valid: false`이면서 `normalized`가 `original`과 다를 때만 그 `normalized` 값을 쓴다. `normalized`가 `original`과 같으면(미등록 area 등 스크립트가 못 고치는 건) 그 태그를 쓰지 말고 문맥 의존 건과 함께 보고에 남겨 메인 스레드가 확정하게 한다. 절차 전문은 `improvement-planner` 정의 §태그 작성.

> tag-validator 위임 금지 — 서브에이전트는 다른 서브에이전트를 호출할 수 없다(도구 목록에 `Agent` 없음).

### Step 6: 보고

생성된 노트 요약:
- 개선 내용 (1-2줄)
- 영향 범위
- Todo 항목 수
- 검증 필요 사항
