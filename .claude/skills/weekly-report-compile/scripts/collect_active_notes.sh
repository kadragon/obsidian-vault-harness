#!/usr/bin/env bash
# collect_active_notes.sh [vault_path]
# 활성(open/active/in-progress) 상태 노트 경로를 세 영역에서 수집하여 출력
VAULT=${1:-.}

echo "=== 12_Projects ==="
grep -rlE "^status:[[:space:]]*\"?(open|active|in-progress)\"?" \
  "$VAULT/12_Projects/" 2>/dev/null

echo "=== 10_Areas ==="
grep -rlE "^status:[[:space:]]*\"?(open|active|in-progress)\"?" \
  "$VAULT/10_Areas/" 2>/dev/null

echo "=== 14_Changes ==="
grep -rlE "^status:[[:space:]]*\"?(open|in-progress)\"?" \
  "$VAULT/14_Changes/" 2>/dev/null
