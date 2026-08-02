#!/bin/bash
# PostToolUse hook: 볼트 노트 Write/Edit 후 태그 검증
# stdin으로 JSON 입력 받음: { "tool_name": "...", "tool_input": { "file_path": "..." }, ... }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VAULT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

command -v python3 &>/dev/null || { echo 'validate-tags: python3 not found — tag validation skipped' >&2; exit 0; }

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
elif [[ "$FILE_PATH" =~ ^[A-Za-z]:[\\/] ]]; then
    _drive=$(echo "${FILE_PATH:0:1}" | tr 'A-Z' 'a-z')
    _rest="${FILE_PATH:3}"
    FILE_PATH="/${_drive}/${_rest//\\//}"
fi

# Skip if not a vault .md file (case-insensitive path comparison for Windows)
[[ "$FILE_PATH" != *.md ]] && exit 0
FILE_PATH_LC=$(echo "$FILE_PATH" | tr 'A-Z' 'a-z')
VAULT_ROOT_LC=$(echo "$VAULT_ROOT" | tr 'A-Z' 'a-z')
[[ "$FILE_PATH_LC" != "$VAULT_ROOT_LC"/* ]] && exit 0

# Skip harness dirs, templates, and non-note files
[[ "$FILE_PATH" == *"/.claude/"* ]] && exit 0
[[ "$FILE_PATH" == *"/99_Template/"* ]] && exit 0
[[ "$FILE_PATH" == *"/docs/"* ]] && exit 0

# Check if file exists
[[ ! -f "$FILE_PATH" ]] && exit 0

# Strip fenced code blocks (``` ... ```) and inline code (`...`) so that
# Dataview/Tasks query tags (e.g. `tag includes #업무/X`) and documentation
# example tags (e.g. `#업무/{도메인}`) are NOT flagged as real tags.
CLEANED=$(awk '/^[[:space:]]*```/{f=!f; next} !f' "$FILE_PATH" | sed 's/`[^`]*`//g')

VIOLATIONS=""

# --- #업무 / #부서 tag validation (delegated to validate_tag.py) ---
# Single source of truth for tag rules is the tag-normalize skill's script:
# it covers the form checks this hook used to re-implement in regex (forbidden
# prefixes, parentheses, unregistered areas) AND the semantic ones a regex
# cannot do (직급 매핑, 부서명 매핑, P_ 접두어, 퇴직/ 경로). Re-implementing
# them here would let the two copies drift.
VALIDATE_TAG="$SCRIPT_DIR/../lib/validate_tag.py"
[[ -f "$VALIDATE_TAG" ]] || { echo "validate-tags: $VALIDATE_TAG not found — tag validation skipped" >&2; exit 0; }

# Placeholder tags in docs/templates (`#업무/{area}`, `#부서/{부서명}/...`) are
# markup, not real tags — drop anything holding a brace.
TAGS=$(grep -oE '#(업무|부서)/[^ 	"]*' <<< "$CLEANED" 2>/dev/null | grep -v '[{}]' | sort -u)

if [[ -n "$TAGS" ]]; then
  # exit 1 == "some tag needs fixing", not a failure — don't let it kill the hook
  TAG_JSON=$(printf '%s\n' "$TAGS" | python3 "$VALIDATE_TAG" - --json 2>/dev/null || true)
  if [[ -n "$TAG_JSON" ]]; then
    TAG_REPORT=$(python3 -c "
import json, sys
try:
    results = json.loads(sys.argv[1])
except json.JSONDecodeError:
    sys.exit(0)
lines = []
for r in results:
    if r.get('valid'):
        continue
    line = '  - ' + r['original']
    if r.get('normalized') and r['normalized'] != r['original']:
        line += ' → ' + r['normalized']
    lines.append(line)
    lines.extend('      · ' + i for i in r.get('issues', []))
print('\n'.join(lines))
" "$TAG_JSON" 2>/dev/null)
    if [[ -n "$TAG_REPORT" ]]; then
      VIOLATIONS="${VIOLATIONS}\n${TAG_REPORT}"
    fi
  fi
fi

# --- #부서 tag placement ---
# Stays here, not in validate_tag.py: that script sees a bare tag string and
# cannot know where in the file it sat. Frontmatter = between the --- lines.
FRONTMATTER_DEPT=$(awk '/^---$/{if(++c==2)exit}c==1' "$FILE_PATH" 2>/dev/null | grep '#부서/')
if [[ -n "$FRONTMATTER_DEPT" ]]; then
  VIOLATIONS="${VIOLATIONS}\n  - #부서 태그가 frontmatter에 있음 (본문으로 이동 필요)"
fi

# Output violations if any — hookSpecificOutput JSON so Claude sees the warning
if [[ -n "$VIOLATIONS" ]]; then
  MSG="[태그 검증 경고] $(basename "$FILE_PATH")"$'\n'"위반 사항:$(printf '%b' "$VIOLATIONS")"$'\n'"tag-validator 에이전트를 실행하여 태그를 정규화하세요."
  python3 -c "import json,sys; print(json.dumps({'hookSpecificOutput':{'hookEventName':'PostToolUse','additionalContext':sys.argv[1]}}))" "$MSG"
fi
