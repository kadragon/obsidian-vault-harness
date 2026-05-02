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
