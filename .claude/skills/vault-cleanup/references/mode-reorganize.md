# Mode 2: reorganize — 폴더 구조 통일

## 목표 구조

```
90_Archive/{area}/YYYY/YYYYMM_문서명/문서.md
```

카테고리 폴더 정보는 문서 frontmatter에 `#업무/{area}/{category}` 태그로 보존한다.

## 실행 절차

### Step 1: 현재 구조 분석

각 area 폴더의 구조 패턴을 파악한다:
- **패턴 A**: `{area}/YYYYMM_문서/` — 플랫 (연도 폴더 없음)
- **패턴 B**: `{area}/카테고리/YYYYMM_문서/` — 카테고리 구조
- **패턴 C**: `{area}/카테고리/YYYY/YYYYMM_문서/` — 카테고리+연도
- **정상**: `{area}/YYYY/YYYYMM_문서/` — 이미 목표 구조

구조 스캔은 `scripts/reorg_archive.py scan-structure` 사용을 우선한다. 원시 탐색이 필요하면:

```bash
# 각 area별 연도폴더/카테고리/플랫문서 수 확인
for dir in */; do
  has_year=$(find "$dir" -mindepth 1 -maxdepth 1 -type d -regex '.*/[0-9][0-9][0-9][0-9]$' | wc -l)
  has_category=$(find "$dir" -mindepth 1 -maxdepth 1 -type d ! -regex '.*/[0-9].*' | wc -l)
  has_dated=$(find "$dir" -mindepth 1 -maxdepth 1 -type d -regex '.*/[0-9][0-9][0-9][0-9][0-9][0-9]_.*' | wc -l)
  echo "$dir → 연도: $has_year, 카테고리: $has_category, 플랫: $has_dated"
done
```

### Step 2: 중복 문서 탐지 및 제거

카테고리 폴더와 연도 하위폴더에 동일 문서가 있는 경우:

```bash
# 중복 탐지 패턴: {cat}/YYYYMM_doc <=> {cat}/YYYY/YYYYMM_doc
for cat in {카테고리폴더}; do
  for yeardir in "$cat"/20??; do
    for item in "$yeardir"/2*_*; do
      base=$(basename "$item")
      if [ -e "$cat/$base" ]; then
        echo "DUP: $cat/$base"
      fi
    done
  done
done
```

연도 하위폴더 쪽을 보존하고, 상위 중복본을 삭제한다. 사용자에게 중복 목록을 먼저 보여준다.

### Step 3: `scripts/reorg_archive.py apply-reorg`로 재구조화

이동은 스크립트에 위임한다 (dry-run → apply 2단계). 스크립트가 처리하는 것:

1. 모든 area 순회
2. 각 문서 폴더(YYYYMM_로 시작)를 `{area}/YYYY/` 아래로 이동
3. 빈 폴더 제거

스크립트가 **하지 않는 것**: `#업무/{area}/{category}` 태그 추가. frontmatter 편집은 포맷 변형이 많아 LLM이 직접 처리한다.

태그 추가 시 기존 frontmatter 형식 감지:
- `tags:` (YAML 배열) → `  - 업무/{area}/{category}` 행 추가
- `tag:` (단일 라인) → 끝에 `업무/{area}/{category}` 추가
- 태그 없음 → `tags:` 필드 새로 생성
- 이미 해당 태그가 있으면 건너뜀

**DRY RUN을 먼저 실행**하여 이동/태그 목록을 사용자에게 보여주고, 확인 후 실제 실행한다.

### Step 4: 최종 확인

```bash
# 모든 문서가 {area}/YYYY/ 안에 있는지 확인
python3 -c "
from pathlib import Path; import re
for md in Path('.').rglob('*.md'):
    parts = md.relative_to('.').parts
    if len(parts) >= 2 and not re.match(r'^\d{4}$', parts[1]):
        print(f'ORPHAN: {md}')
"
```

### Step 5: `10_Areas/` 무첨부 래퍼 폴더 스윕

Step 1~4와 대상이 다르다 — 여기부터는 `90_Archive/`가 아니라 **`10_Areas/`** 를 본다.

`conventions.md` 규칙: 첨부가 없으면 래퍼 폴더 없이 area 루트에 단일 `.md`. `check-folder-rules.py`가 이 규칙을 훅으로 강제하지만 폴더 생성 직후 60초 유예에 걸려 **최초 생성 경로에서는 검출되지 않는다**. 잔존분은 이 스윕으로 찾는다.

```bash
python3 .claude/skills/vault-cleanup/scripts/reorg_archive.py \
  find-bare-wrappers 10_Areas --json
```

각 항목: `current`(래퍼 폴더) · `note`(안쪽 노트, 빈 폴더면 `""`) · `suggested`(평탄화 대상 경로, `_` 접두어 제거) · `area` · `target_occupied`.

첨부는 **재귀로** 센다 — `{wrapper}/2026-012/결과물/x.pdf`처럼 하위 폴더에 든 첨부도 첨부로 친다.

**`target_occupied: true`인 항목은 절대 그냥 `mv` 하지 말 것.** `suggested` 경로에 이미 다른 노트가 있다는 뜻이고, POSIX `mv`는 대상을 덮어쓴다 — 노트는 gitignore라 복구 불가다. 이름을 바꿔 옮기거나 두 노트를 먼저 병합한다.

**스크립트는 탐지만 한다 — 이동은 없다.** 결과를 사용자에게 목록으로 보여주고 승인을 받은 뒤 `git mv`/`mv`로 개별 평탄화한다 (안전 규칙 #1). 노트를 옮기면 기존 wikilink가 깨질 수 있으므로 이동 전 `rg -F "<노트명>"` 으로 참조를 확인한다.

`note`가 `""`인 항목은 노트 없이 폴더만 남은 잔해다 — 첨부 추가 예정인지 사용자에게 확인한 뒤 비었으면 제거한다.
