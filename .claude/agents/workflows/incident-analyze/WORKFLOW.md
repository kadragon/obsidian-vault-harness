> **Agent workflow — not a skill.** `incident-analyst` 에이전트가 인시던트 노트 작성 시 Read로 읽는 절차서다.
> Skill 툴로 호출되지 않는다. 소유 에이전트: `.claude/agents/incident-analyst.md`

# Incident Analysis

Analyze 통합학사시스템 errors and produce a structured incident note.

## 워크플로우

### Step 0: 사전 컨텍스트 확인

에러 로그에서 도메인(프로시저명·메뉴코드)을 먼저 추출한 뒤:

1. `qmd search "{도메인}-운영-MOC" -n 3` — 기존 운영 MOC 존재 여부 확인
2. MOC가 있으면 `## 반복 인시던트 패턴` 섹션을 참조하여 이미 알려진 유형인지 확인
3. 기존 패턴과 일치하면 이후 분석 단계에서 해당 패턴 우선 참조

### Step 1: 에러 로그 파싱

에러 로그에서 다음 핵심 정보를 추출한다:

| 필드 | 추출 위치 | 예시 |
|------|----------|------|
| 프로시저/서비스 | `serviceName`, `methodName` | `Hl0927Service/save01SinchList` |
| 메뉴 코드 | `mc`, `REQUEST_MENU_CD` | `3020927` |
| 에러 타입 | Exception 클래스명 | `SQLIntegrityConstraintViolationException` |
| 발생 일시 | 로그 타임스탬프 | `2025-06-16 11:16:37` |
| 사용자 정보 | `SESSION_USER_ID`, IP 등 | `310071` |
| 관련 파라미터 | `PARAMETER_INFO` 내 핵심 값 | 학번, 년도, 학기 등 |

파라미터에서 업무 맥락을 파악한다. YEAR, HAKGI, HAKBEON 등은 학사 데이터의 핵심 키이다.

에러 로그가 불완전하면 분석 가능한 부분만 진단하고 누락 정보를 명시한다.

### Step 2: 유사 인시던트 검색

다음 순서로 검색한다 (`**` glob으로 상반기/하반기 하위 폴더 포함):

1. **QMD 검색**: `qmd search "{프로시저명} {에러타입}" -n 10` — 관련 노트 빠르게 탐색
2. **프로시저명으로 정확 매칭**: `14_Changes/incident/` 하위에서 동일 프로시저명 Grep
3. **메뉴 코드로 정확 매칭**: 7자리 메뉴 코드로 Grep
4. **시맨틱 유사 검색**: `qmd vsearch "{에러 상황 설명}" -n 5` — 유사 증상 인시던트 발견
5. **Archive 확장**: `90_Archive/` 하위에서 동일 업무 영역 Grep

검색 결과가 있으면 과거 해결 방안을 참조하여 진단에 활용한다.

### Step 3: 근본 원인 진단

에러 타입별 주요 원인·확인 포인트·통합학사시스템 반복 패턴 → `references/error-types.md`

진단은 로그 근거 기반으로 한다. 추측일 경우 "추정"으로 명시한다.

에러 분석 결과 시스템 개선이 필요한 경우, improvement-planner 연계를 제안한다.

### Step 4: 인시던트 노트 생성

#### 경로 + 파일명 (스크립트 위임)

반기 판단, 경로 조합, 순번 결정은 모두 `scripts/new_incident_path.py`로 위임한다. LLM이 직접 Glob·카운팅을 수행하지 말 것.

```bash
python3 .claude/agents/workflows/incident-analyze/scripts/new_incident_path.py {YYYY-MM-DD}
```

출력 예: `/Users/.../14_Changes/incident/2026/상반기/통합학사시스템 오류 처리 2026-04-10_3.md`

스크립트가 하는 일: 발생월 1~6 → `상반기` / 7~12 → `하반기`, 같은 날짜의 기존 파일을 NFC 정규화 후 스캔해 최대 순번 + 1. 파일은 생성하지 않고 경로만 반환한다.

파일명 `통합학사시스템 오류 처리 {YYYY-MM-DD}_{순번}.md`은 **단일 명명규칙으로 mechanical 강제**된다 (`check-folder-rules.py` Rule 4, PostToolUse Write). 다른 형식(`Error_*`, `오류 처리 *` 등)으로 생성 시 경고. 반드시 위 스크립트 출력 경로를 사용할 것.

#### 중복 방지

동일 프로시저 + 동일 에러 타입 + 동일 날짜의 인시던트가 이미 존재하면 신규 노트를 생성하지 않는다. 기존 노트의 `## 프로시저`와 `## 오류 구분` 섹션을 읽어 비교한다. 중복이면 기존 노트 경로를 보고하고 재발 여부만 사용자에게 확인한다.

#### 노트 구조

`99_Template/_인시던트.md` 템플릿을 기준으로 한다. 각 섹션을 다음과 같이 채운다:

| 섹션 | 채우는 내용 |
|------|-----------|
| frontmatter | `type: change`, `change_type: incident`, `status: open` (`date created`/`date modified`는 Linter가 자동 관리 -- 직접 넣지 않음). 공문으로 접수된 장애면 `doc_date: YYYY-MM-DD`(공문 시행일), 접수일이 다를 때만 `recv_date` 추가 -- `99_Template/_메타데이터 규칙.md` |
| `#` 제목 | `통합학사시스템 오류 처리 {YYYY-MM-DD}_{순번}` |
| `## 관련` | 태그는 **직접 작성** (`validate_tag.py --json`으로 검증. tag-validator 위임 금지 — 서브에이전트는 서브에이전트를 호출할 수 없다). 형식: `#부서/{부서명}/{직급}_{이름}` + `#업무/{영역}/{하위영역}/{메뉴명}` |
| `## 발생 정보` | 발생 일시 (`YYYY-MM-DD HH:mm`) + 기타 맥락 |
| `## 프로시저` | `{ServiceName/methodName}` |
| `## 메뉴 위치` | `{메뉴코드}` (텍스트 경로만; 태그는 `## 관련`으로) |
| `## 오류 구분` | Exception 클래스명 |
| `### PARAMETER_INFO` | 핵심 파라미터만 발췌 (code block) |
| `### ERR_INFO` | 에러 메시지 (code block) |
| `## 관련 문서` | **실제 관련 문서(과거 유사 인시던트 노트, 설계 문서, 운영 MOC 등) 있을 때만 포함**. 없으면 섹션(헤딩+콜아웃) 전체를 생략 — 빈 `[[ ]]` 플레이스홀더 금지 |
| `## 할 일` | `- [ ] {진단 기반 처리 항목} 📅 {YYYY-MM-DD} ➕ {오늘 날짜}` |
| `## 처리 결과` | 해결 후 결론 (완료 시 기록) |

**사용자 정보 부족 시**: SESSION_USER_ID만 있고 부서명/사용자명을 특정할 수 없으면 `#부서/` 태그 없이 `## 발생 정보`에 `SESSION_USER_ID: {id}`로 기록한다.

### Step 5: Wiki 피드백

노트 생성 직후 `_Wiki/contracts.md` Wiki Feedback Payload 규칙에 따라 **직접 수행**한다 (Read + Edit). obsidian-operator 위임 금지 — 이 스킬은 서브에이전트(incident-analyst)가 읽으며, **서브에이전트는 다른 서브에이전트를 호출할 수 없다**(도구 목록에 `Agent` 없음). 과거 위임 지시는 실행 불가였다.

1. **log.md append**: `- {오늘날짜} #incident [[{노트 경로}]] — {도메인} 생성`
2. **MOC 확인**: `_Wiki/topics/{도메인}-운영-MOC.md` 존재 여부 점검
   - 존재 → **양방향**: MOC `## 반복 인시던트 패턴`에 wikilink append + 이 노트 `## 관련 문서`에 `- 운영 MOC: [[{도메인}-운영-MOC]]` 역링크 추가 (contracts.md MOC 갱신 조건)
   - 없음 → 동일 도메인 인시던트 수 `qmd search "{도메인} incident" --json -n 20`으로 카운트 → 3건+ 이면 "운영 MOC 생성을 권장합니다" 보고

### Step 6: 보고

분석 결과를 요약 보고한다:
- 에러 원인 (1-2줄)
- 유사 과거 사례 유무
- 권장 처리 방안
- 추가 확인이 필요한 사항

---

## 참고 자료

- **`references/error-types.md`** — 에러 타입별 진단 가이드, 통합학사시스템 반복 패턴
