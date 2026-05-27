#!/bin/bash
# PostToolUse hook: 볼트 노트 Write/Edit 후 태그 검증
# stdin으로 JSON 입력 받음: { "tool_name": "...", "tool_input": { "file_path": "..." }, ... }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VAULT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Read JSON from stdin
INPUT=$(cat)

# Extract file_path from tool_input
FILE_PATH=$(echo "$INPUT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
inp = data.get('tool_input', {})
print(inp.get('file_path', inp.get('filePath', '')))
" 2>/dev/null)

# Skip if no file path
[[ -z "$FILE_PATH" ]] && exit 0

# Normalize Windows path (C:\foo\bar → /c/foo/bar) to match bash VAULT_ROOT
if command -v cygpath &>/dev/null; then
    FILE_PATH=$(cygpath -u "$FILE_PATH" 2>/dev/null || echo "$FILE_PATH")
elif [[ "$FILE_PATH" =~ ^[A-Za-z]:\\ ]]; then
    _drive=$(echo "${FILE_PATH:0:1}" | tr 'A-Z' 'a-z')
    _rest="${FILE_PATH:3}"
    FILE_PATH="/${_drive}/${_rest//\\//}"
fi

# Skip if not a vault .md file (case-insensitive path comparison for Windows)
[[ "$FILE_PATH" != *.md ]] && exit 0
FILE_PATH_LC=$(echo "$FILE_PATH" | tr 'A-Z' 'a-z')
VAULT_ROOT_LC=$(echo "$VAULT_ROOT" | tr 'A-Z' 'a-z')
[[ "$FILE_PATH_LC" != "$VAULT_ROOT_LC"/* ]] && exit 0

# Skip .claude/ directory, templates, and non-note files
[[ "$FILE_PATH" == *"/.claude/"* ]] && exit 0
[[ "$FILE_PATH" == *"/99_Template/"* ]] && exit 0

# Check if file exists
[[ ! -f "$FILE_PATH" ]] && exit 0

# --- #업무 tag validation ---
FORBIDDEN_PREFIXES=(
  '#업무/인트라넷/'
  '#업무/부속/'
  '#업무/행정/'
  '#업무/학사/'
  '#업무/공통/'
  '#업무/시스템/'
  '#업무/직원서비스/'
  '#업무/학생서비스/'
  '#업무/교수서비스/'
)

VIOLATIONS=""

for PREFIX in "${FORBIDDEN_PREFIXES[@]}"; do
  FOUND=$(grep -o "${PREFIX}[^ 	]*" "$FILE_PATH" 2>/dev/null)
  if [[ -n "$FOUND" ]]; then
    VIOLATIONS="${VIOLATIONS}\n  - ${FOUND}"
  fi
done

# Check parentheses in #업무 tags
PAREN_FOUND=$(grep -oE '#업무/[^ 	]*\(' "$FILE_PATH" 2>/dev/null)
if [[ -n "$PAREN_FOUND" ]]; then
  VIOLATIONS="${VIOLATIONS}\n  - 괄호 사용: ${PAREN_FOUND}"
fi

# Check allowed areas
ALLOWED_AREAS="수업성적|홈페이지|일반서무|개발공통|장학|전임교원공채|시설물이용|졸업|코러스|등록|교육연구학생지도|기타|예산관리|교직|교수업적|수강신청|구전자문서|학적"

UNKNOWN_AREAS=$(grep -oE '#업무/[^/ 	]+' "$FILE_PATH" 2>/dev/null | grep -vE "^#업무/(${ALLOWED_AREAS})$" | grep -v '#업무/{area}' | sort -u)
if [[ -n "$UNKNOWN_AREAS" ]]; then
  VIOLATIONS="${VIOLATIONS}\n  - 미등록 area: ${UNKNOWN_AREAS}"
fi

# --- #부서 tag validation ---
# Check if #부서 tags are in frontmatter (between --- lines)
FRONTMATTER_DEPT=$(awk '/^---$/{if(++c==2)exit}c==1' "$FILE_PATH" 2>/dev/null | grep '#부서/')
if [[ -n "$FRONTMATTER_DEPT" ]]; then
  VIOLATIONS="${VIOLATIONS}\n  - #부서 태그가 frontmatter에 있음 (본문으로 이동 필요)"
fi

# Output violations if any
if [[ -n "$VIOLATIONS" ]]; then
  echo "[태그 검증 경고] $(basename "$FILE_PATH")"
  echo -e "위반 사항:${VIOLATIONS}"
  echo ""
  echo "tag-validator 에이전트를 실행하여 태그를 정규화하세요."
fi
