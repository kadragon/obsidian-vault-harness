#!/bin/bash
# Legacy entry point, kept because docs and agents run it by name
# (e.g. `printf '{"tool_input":{"file_path":"<abs path>"}}' | bash .claude/hooks/validate-tags.sh`).
# The logic lives in check-tags.py; settings.json runs it through post-write.py.
exec python3 "$(dirname "${BASH_SOURCE[0]}")/check-tags.py"
