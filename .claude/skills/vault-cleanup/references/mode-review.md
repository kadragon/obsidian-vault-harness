# Mode 1: review — 문서 가치 점검

아카이브 문서를 haiku 에이전트로 읽고, 보관 가치가 낮은 문서를 식별한다.

## 삭제 후보 기준 (LOW value)

- **단순 권한 부여 / 비밀번호 초기화** — 당일 처리, 시스템 변경 없음
- **단순 문의 → 즉시 안내 종료** — 메뉴 위치 안내, FAQ성 답변
- **일회성 행정 처리** — 교육 신청, 공문 전달, 물품 배부, 배너 게시
- **특정 학생 1~2명 데이터 수정/삭제** — 개별 건, 패턴 아님
- **빈 문서 / 미완성 문서** — 프론트매터만 있거나 처리 결과 미기록
- **중복 문서** — 동일 내용이 복수 위치에 존재

## 보관 기준 (HIGH value)

- SQL/프로시저 수정 기록이 있는 오류 해결
- 정책·규정 변경에 따른 시스템 개선
- 반복 발생 문제의 패턴을 보여주는 문서
- 기능 개발/개선 이력 (코드 변경 포함)
- 외부 시스템 연동 문제 분석

## 실행 절차

### Step 1: 폴더별 문서 수 확인

볼트 루트에서 실행 (볼트 루트 경로는 런타임에 확정):

```bash
cd 90_Archive
for dir in */; do
  count=$(find "$dir" -name "*.md" | wc -l)
  echo "$count $dir"
done | sort -rn
```

### Step 2: haiku 에이전트 병렬 배포

폴더별로 haiku 모델 에이전트를 배포한다. 문서가 적은 폴더(10개 이하)는 묶어서 하나의 에이전트에 맡긴다.

```
Agent(
  model: "haiku",
  run_in_background: true,
  prompt: """
  You are reviewing archived documents in an Obsidian vault for a Korean university IT operations team.
  Your task is to identify documents with LOW archival value in the folder `90_Archive/{area}/` (relative to the vault root).

  Steps:
  1. List all .md files in the folder and its subfolders
  2. Read each document (first 30-50 lines)
  3. Evaluate archival value using the criteria below

  LOW value criteria: [위의 삭제 후보 기준 삽입]
  HIGH value criteria: [위의 보관 기준 삽입]

  Output format (Korean):
  ## {area} 폴더 점검 결과
  총 문서 수: N개
  보관 가치 낮음(삭제 후보): M개

  ### 삭제 후보 목록
  | 파일명 | 사유 |
  |--------|------|
  | ... | ... |
  """
)
```

### Step 3: 결과 종합 → 사용자에게 제시

모든 에이전트 완료 후, 폴더별 결과를 하나의 테이블로 종합한다:

```markdown
| 폴더 | 총 문서 | 삭제 후보 | 비율 | 주요 사유 |
|------|---------|----------|------|----------|
```

**삭제는 사용자 확인 후에만 실행한다.** 절대 자동 삭제하지 않는다.

### Step 4: 사용자 승인 시 삭제 실행 (.trash 이동)

**`rm -rf` 금지.** 볼트 노트는 git-ignore 대상이라 hard delete는 복구 불가하다. 삭제는 `reorg_archive.py purge`로 위임하면 `<볼트>/.trash/<타임스탬프>/`로 **이동**(복구 가능)한다. dry-run이 기본이며 `--apply`로 실제 실행한다.

승인된 삭제 후보 폴더마다:

```bash
# dry-run (기본) — 무엇이 어디로 갈지 확인
python3 .claude/skills/vault-cleanup/scripts/reorg_archive.py purge \
  "90_Archive/.../삭제대상폴더" "$(git -C . rev-parse --show-toplevel)"

# 승인 후 실제 이동
python3 .claude/skills/vault-cleanup/scripts/reorg_archive.py purge \
  "90_Archive/.../삭제대상폴더" "$(git -C . rev-parse --show-toplevel)" --apply
```

스크립트는 볼트 밖 경로·볼트 루트·`.trash` 자체는 거부한다. 사용자가 `.trash`를 확인 후 직접 비운다.

빈 디렉토리 정리만 `find`로 수행한다 (디렉토리는 노트가 아니므로 trash 불필요):

```bash
find 90_Archive -type d -empty -delete
```
