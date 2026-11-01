#!/usr/bin/env bash
# Preserve the existing entry point and delegate parsing to the portable collector.
exec python3 "$(dirname "$0")/collect_active_notes.py" "$@"
