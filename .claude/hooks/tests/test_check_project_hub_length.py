#!/usr/bin/env python3
"""Regression tests for the project hub length advisory.

Run with: python3 .claude/hooks/tests/test_check_project_hub_length.py
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unicodedata
import unittest
from pathlib import Path


HERE = Path(__file__).resolve()
HOOK = HERE.parents[1] / "check-project-hub-length.py"


def run_hook(rel_path: str, lines: int, relative: bool = False, raw: bytes | None = None) -> str:
    with tempfile.TemporaryDirectory() as directory:
        note = Path(directory) / rel_path
        note.parent.mkdir(parents=True)
        note.write_text("\n".join(f"line {i}" for i in range(lines)) + "\n", encoding="utf-8")
        if raw is not None:
            note.write_bytes(raw)
        payload = json.dumps({"tool_input": {"file_path": rel_path if relative else str(note)}})
        result = subprocess.run(
            [sys.executable, str(HOOK)],
            input=payload,
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=True,
            cwd=directory,
        )
    if not result.stdout.strip():
        return ""
    return json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]


HUB = "12_Projects/2026/사업A/_사업A.md"


class ProjectHubLengthTests(unittest.TestCase):
    def test_long_hub_warns_with_skill_name(self) -> None:
        warning = run_hook(HUB, 121)
        self.assertIn("project-restructure", warning)
        self.assertIn("121", warning)

    def test_hub_at_threshold_is_silent(self) -> None:
        self.assertEqual(run_hook(HUB, 120), "")

    def test_non_hub_note_in_project_is_silent(self) -> None:
        self.assertEqual(run_hook("12_Projects/2026/사업A/_협업게시판-모니터링.md", 300), "")

    def test_stage_note_is_silent(self) -> None:
        self.assertEqual(run_hook("12_Projects/2026/사업A/3. 과업심의/_3. 과업심의.md", 300), "")

    def test_hub_without_year_folder_warns(self) -> None:
        self.assertNotEqual(run_hook("12_Projects/사업B/_사업B.md", 200), "")

    def test_nfd_folder_name_still_matches(self) -> None:
        name = unicodedata.normalize("NFD", "사업C")
        rel = f"12_Projects/2026/{name}/_{unicodedata.normalize('NFC', '사업C')}.md"
        self.assertNotEqual(run_hook(rel, 200), "")

    def test_vault_relative_path_warns(self) -> None:
        self.assertNotEqual(run_hook(HUB, 200, relative=True), "")

    def test_non_utf8_hub_is_silent(self) -> None:
        self.assertEqual(run_hook(HUB, 0, raw=b"\xff\xfe\x00bad\n" * 200), "")

    def test_outside_projects_is_silent(self) -> None:
        self.assertEqual(run_hook("10_Areas/학사/_학사.md", 300), "")


if __name__ == "__main__":
    unittest.main()
