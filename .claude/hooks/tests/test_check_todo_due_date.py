#!/usr/bin/env python3
"""Regression tests for task-date validation semantics.

Run with: python3 .claude/hooks/tests/test_check_todo_due_date.py
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve()
HOOK = HERE.parents[1] / "check-todo-due-date.py"


def run_hook(content: str) -> str:
    with tempfile.TemporaryDirectory() as directory:
        note = Path(directory) / "note.md"
        note.write_text(content, encoding="utf-8")
        payload = json.dumps({"tool_input": {"file_path": str(note)}})
        result = subprocess.run(
            [sys.executable, str(HOOK)],
            input=payload,
            text=True,
            capture_output=True,
            check=True,
        )
    if not result.stdout.strip():
        return ""
    output = json.loads(result.stdout)
    return output["hookSpecificOutput"]["additionalContext"]


class TodoDateHookTests(unittest.TestCase):
    def test_unknown_deadline_is_allowed(self) -> None:
        warning = run_hook("- [ ] Investigate ➕ 2026-09-09\n")
        self.assertEqual(warning, "")

    def test_explicit_weekend_deadline_is_preserved(self) -> None:
        warning = run_hook("- [ ] Weekend release ➕ 2026-09-09 📅 2026-09-12\n")
        self.assertEqual(warning, "")

    def test_explicit_invalid_deadline_is_reported(self) -> None:
        warning = run_hook("- [ ] Investigate ➕ 2026-09-09 📅 2026-02-30\n")
        self.assertIn("2026-02-30", warning)
        self.assertIn("유효하지 않음", warning)

    def test_invalid_date_token_is_reported(self) -> None:
        warning = run_hook("- [ ] Investigate ➕ 2026-09-09 📅 TBD\n")
        self.assertIn("TBD", warning)
        self.assertIn("YYYY-MM-DD", warning)

    def test_completed_item_keeps_due_optional_but_requires_completion_date(self) -> None:
        warning = run_hook("- [x] Finished ➕ 2026-09-09\n")
        self.assertIn("✅", warning)
        self.assertNotIn("📅", warning)


if __name__ == "__main__":
    unittest.main()
