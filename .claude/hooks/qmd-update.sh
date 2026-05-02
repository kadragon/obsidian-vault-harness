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

# Skip if no file path or not a vault .md file
[[ -z "$FILE_PATH" ]] && exit 0
[[ "$FILE_PATH" != "$VAULT_ROOT"/*.md ]] && exit 0

# Skip .claude/ directory and templates
[[ "$FILE_PATH" == *"/.claude/"* ]] && exit 0
[[ "$FILE_PATH" == *"/99_Template/"* ]] && exit 0

# Run QMD update in background (incremental, fast)
(qmd update --quiet && qmd embed --quiet) &>/dev/null &

exit 0
