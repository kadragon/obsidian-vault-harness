# Eval Criteria

Note quality evaluation for `통합학사시스템` vault. Agent creates note (generator); separate evaluation pass checks it (evaluator). Separation prevents leniency drift.

## Criteria

### 1. Frontmatter Completeness (30%)

All required fields present and non-empty.

| Score | Description |
|-------|-------------|
| 5 | All required fields present, values conform to schema (`type`, `status` enum-valid) |
| 3 | `change_type` missing on a change note (incident/improvement) |
| 1 | `type` or `status` missing, or `status` not in enum |

Required frontmatter by note kind (per `99_Template/_메타데이터 규칙.md` — `date created`/`date modified` are Linter-managed, NOT authored; 태그는 본문 `## 관련` 인라인, frontmatter 아님):
- `_업무사안.md` (work) — `type: work`, `status`
- `_인시던트.md` (change) — `type: change`, `change_type: incident`, `status`
- `_개선.md` (change) — `type: change`, `change_type: improvement`, `status`
- `_교육.md` (training) — `type: training`, `status`

`status` 허용값: `open | in-progress | hold | closed | active` (그 외는 위반).

**선택 필드 `doc_date` / `recv_date`** (2026-07-30 신설, 공문 유래 노트) — 있으면 `YYYY-MM-DD` 형식이어야 하며 `check-template.py` Check 2c가 검사한다. **부재는 감점 아님**(공문 아닌 건은 생략이 정상). 단 값이 있으면 **원본 시행일·접수일과 일치하는지는 사실검증 대상**이다.

**How to test:** `python3` 또는 Read로 frontmatter 파싱 — `type` 존재, `status` enum 일치, change 노트는 `change_type` 확인. `check-template.py` 훅과 동일 기준.

### 2. Tag Correctness (25%)

`#업무/` and `#부서/` tags follow `docs/conventions.md` → tag rules.

| Score | Description |
|-------|-------------|
| 5 | Tags pass `validate-tags.sh` and are semantically correct |
| 3 | Mechanical form correct; area assignment questionable |
| 1 | Forbidden prefix, unknown area, or tag missing entirely |

**How to test:** 훅에 노트 **절대경로**를 PostToolUse JSON으로 먹인다 — `printf '{"tool_input":{"file_path":"<절대경로>"}}' | bash .claude/hooks/validate-tags.sh` (인자 없이 호출하거나 상대경로면 stdin이 비어 무음 통과한다). 그 다음 area 배정이 노트 내용과 맞는지 판단한다.

> **훅 무음 ≠ 태그 존재.** `validate-tags.sh`는 **발견한 태그의 형식**만 검증하므로 태그가 하나도 없으면 무음이다. `#업무/` 부재는 `check-template.py` Check 5가 별도로 잡는다. `#부서/` 부재는 **어느 훅도 잡지 않는다** — 실측 미보유 56/201(28%)로 관행이 아니라 기계화하지 않았다. 이 한 가지는 평가자 판단으로 남는다.

### 3. Template Adherence (25%)

**이 기준은 `check-template.py` Check 4가 기계적으로 판정한다. 평가자는 훅 결과를 신뢰하고 재판정하지 않는다** (2026-07-30). 훅 경고가 없으면 5점이다.

**적용 범위: `10_Areas/`의 `type: work` 노트뿐이다.** `type: reference` 등 다른 종류는 업무사안 템플릿을 쓰지 않는 것이 정상이라 검사하지 않는다.

채점 대상은 **필수 앵커 2개의 존재**뿐이다. 허용 표기는 **두 장치**가 만든다 — (1) 비교 전 선행 기호(이모지·ZWJ·variation selector·구두점) 제거, (2) `할 일`만 동의어 `해결 방안` 추가 허용:

| 앵커 | 동의어 | 통과 예 |
|------|------|------|
| 관련 | 없음 | `## 관련` · `## 🙋‍♂️ 관련` |
| 할 일 | `해결 방안` | `## 할 일` · `## 해결 방안` · `## 🛠 해결 방안` |

**위반이 아닌 것 — 감점하지 말 것:**
- 이모지 별칭 사용 (실측 202건 중 116건이 `## 🙋‍♂️ 관련`, 115건이 `## 🛠 해결 방안` — 다수 관행이다)
- 템플릿 5섹션 외 **자유 섹션 추가** (`## 요청 개요`, `## 이슈 요약`, `## 1. 관련 근거` 등 — 136건이 보유)
- `## 현황`·`## 처리 결과`·`## 관련 문서`를 **근거 없어 생략**한 것 (content-conditional: 실제 내용 없으면 섹션째 생략이 원칙)
- `#` 제목의 날짜 프리픽스 **부재** — 프리픽스 규칙은 폐기됐다(2026-07-30, 준수율 64/202). 날짜는 `doc_date` frontmatter로 기록한다. 프리픽스가 **있는** 것도 감점하지 말 것 (기존 64건은 GP#1로 불변)

| Score | Description |
|-------|-------------|
| 5 | 필수 앵커 2개 존재 (별칭·자유 섹션·content-conditional 생략은 모두 5점) |
| 3 | 필수 앵커 1개 부재 |
| 1 | 필수 앵커 2개 부재; 템플릿 구조 없는 맨 텍스트; **또는 `- [[ ]]` 같은 빈 wikilink 플레이스홀더가 남아있음(생략하지 않고 억지로 채운 흔적)** |

**How to test:** 훅을 직접 돌린다 — `printf '{"tool_input":{"file_path":"<절대경로>"}}' | python3 .claude/hooks/check-template.py`. **`python`이 아니라 `python3`** — 비대화형 셸엔 `python` 별칭이 없어 `command not found`로 죽고, 그 무출력이 "통과"로 오독된다. **경로는 절대경로여야 한다** (상대경로면 훅이 파일을 못 찾아 무음 종료 → 검사한 줄 알고 넘어간다). 무출력이면 기준 1·3·4가 통과다 (기준 2는 `validate-tags.sh` 소관 — 위 기준 2 참조). 헤딩을 눈으로 템플릿과 대조하지 말 것 — 그 방식이 다수 관행을 위반으로 오판한 원인이다.

### 4. Wikilink Style (10%)

Internal links use plain `[[노트명]]`, never `![[embed]]` unless explicitly requested.

| Score | Description |
|-------|-------------|
| 5 | No embeds; all internal links are `[[link]]` style |
| 1 | `![[embed]]` present without explicit user request |

Note: Binary criterion — scores 2/3/4 not applicable. Either embeds exist (1) or they don't (5).

**How to test:** Grep for `![[` in note content.

### 5. Wiki Feedback Loop (10%)

Operational note feeds back into `_Wiki/` when domain threshold reached.

| Score | Description |
|-------|-------------|
| 5 | Domain has <20 notes — no MOC required, note complete |
| 5 | Domain has 20+ notes — MOC exists and this note is linked | ← both map to 5: threshold not triggered in first case |
| 2 | Domain has 20+ notes — MOC exists but note not registered |
| 1 | Domain has 20+ notes — MOC missing entirely |

**How to test:** Count notes in domain. If ≥20, check `_Wiki/topics/{도메인}-운영-MOC.md` exists and references this note.

## Pass Threshold

- All criteria ≥ 3 (no dimension broken)
- Weighted average ≥ 3.5

Below threshold → findings become fixes in same session before note is committed.

## 기계 검사 커버리지 — LLM 평가를 부르기 전에 확인 (2026-07-30)

5개 기준은 **전부 "How to test"가 결정론적**이고, 그중 4개는 이미 훅이 실행한다:

| 기준 | 기계 검사 | 기계가 **못 잡는** 잔여분 |
|------|-----------|-----------|
| 1 Frontmatter | `check-template.py` Check 2·2b·2c·3 (Check 3은 incident·improvement 양쪽) | — |
| 2 Tag | `validate-tags.sh` → `validate_tag.py` (형식) + `check-template.py` Check 5 (`#업무/` **구체** 태그 존재 — `10_Areas`+`type: work`·`14_Changes`·`20_Training`) | `#부서/` 부재(관행 아님, 28%), area 배정의 문맥 적합성 |
| 3 Template Adherence | `check-template.py` Check 1b·4 — **Check 4는 `10_Areas/`+`type: work` 전용** | **`14_Changes/`·`20_Training/`·`12_Projects/`·`11_Routines/` 노트의 섹션 구조는 기계 검사가 없다** — 해당 종류는 평가자가 직접 본다 |
| 4 Wikilink Style | `check-template.py` Check 1 | — |
| 5 Wiki Feedback Loop | `moc_gate.py` (임계 도달 도메인 검출) | MOC **순방향 등록** 여부 — 노트가 MOC를 링크했는지는 grep |

두 훅은 `Write|Edit` PostToolUse로 자동 발동하므로, **노트를 쓴 직후 훅 경고가 없었다면 기준 1·3·4와 기준 2의 형식·`#업무/` 존재분은 이미 통과**다. **단 기준 3은 `10_Areas/`+`type: work` 노트에 한해서다** — incident·improvement·training 노트의 섹션 구조는 훅이 보지 않으므로 훅 무음이 통과가 아니고, 평가자가 해당 `99_Template/` 템플릿과 직접 대조한다(이 종류는 이모지 별칭 오탐 이력이 없다). 이 상태에서 `note-evaluator`를 부르면 훅이 한 계산을 LLM으로 재실행하는 것이고, 실측 비용은 노트 1건당 약 100k 토큰이다. **단 위 표의 "못 잡는 잔여분" 열은 훅이 무음이어도 통과가 아니다** — 형식 검증기는 값이 아예 없는 경우에 무음이 되는 것이 기본 성질이므로, 훅 무음을 전면 통과로 읽지 말 것.

**따라서 `note-evaluator`의 고유 가치는 기계가 못 하는 것 하나뿐이다: 노트 본문 사실이 원본 문서와 일치하는지** (공문 번호·기한·담당자·회차 등). 회차성 반복 공문에서 선례를 베끼다 stale 값이 섞이는 위험이 실재하므로 이 검증은 버리지 않되, **조건부로만** 부른다 — 호출 조건은 `inbox-process/SKILL.md` 5단계.

## Evaluator Protocol

1. 훅 결과 확인 → 훅이 판정한 항목은 그대로 채택한다. 재판정 금지. **단 §기계 검사 커버리지 표의 "못 잡는 잔여분" 열은 직접 확인한다** — 훅 무음이 통과를 뜻하지 않는 항목이다.
2. 기준 5(Wiki Feedback Loop: MOC 순방향 등록)와 **원본 대조 사실검증**에 집중한다.
3. 원본 재추출은 **사실검증 대상 필드에 한정**한다(공문번호·시행/접수일·기한·담당자·회차). 위임자가 추출 산출물 경로를 넘겼으면 그것을 재사용하되, **경로가 오는 것을 전제하지 말 것** — 워커의 반환 계약에 추출본 경로는 없고 `/tmp` 산출물은 워커가 정리했을 수 있다.
4. Below threshold → fix and re-evaluate.
5. All pass → note done.

**Anti-pattern:** "Tag form looks fine so I'll give it a 4 even though the area is wrong." Score follows evidence, not vibes. Each criterion graded independently.
