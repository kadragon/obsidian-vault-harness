#!/bin/bash
# PostToolUse hook: 볼트 노트 Write/Edit 후 QMD 인덱스 증분 갱신
# 백그라운드로 실행하여 응답 지연 없음

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

[[ -z "$FILE_PATH" ]] && exit 0

# Normalize Windows path to Unix form
if command -v cygpath &>/dev/null; then
    FILE_PATH=$(cygpath -u "$FILE_PATH" 2>/dev/null || echo "$FILE_PATH")
elif [[ "$FILE_PATH" =~ ^[A-Za-z]:[\\/] ]]; then
    _drive=$(echo "${FILE_PATH:0:1}" | tr 'A-Z' 'a-z')
    _rest="${FILE_PATH:3}"
    FILE_PATH="/${_drive}/${_rest//\\//}"
fi

# Skip if not a vault .md file
[[ "$FILE_PATH" != "$VAULT_ROOT"/*.md ]] && exit 0

# Skip .claude/ directory and templates
[[ "$FILE_PATH" == *"/.claude/"* ]] && exit 0
[[ "$FILE_PATH" == *"/99_Template/"* ]] && exit 0

# Skip if qmd binary is absent
if ! command -v qmd &>/dev/null; then
    echo "qmd not found; semantic index not updated" >&2
    exit 0
fi

# Run QMD update in background (incremental, fast)
(qmd update --quiet && qmd embed --quiet) &>/dev/null &

exit 0
