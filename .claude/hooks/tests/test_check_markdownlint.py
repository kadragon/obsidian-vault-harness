#!/usr/bin/env python3
"""Regression tests for the markdownlint advisory hook.

Run with: python3 .claude/hooks/tests/test_check_markdownlint.py
Needs node and npm on PATH (skipped otherwise); the first run installs markdownlint-cli2
into the hook's cache (MARKDOWNLINT_CACHE_DIR, default ~/.cache/knue-vault-harness).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve()
HOOK = HERE.parents[1] / "check-markdownlint.py"
CONFIG = HERE.parents[3] / ".markdownlint-cli2.jsonc"

CLEAN = "# 제목\n\n#업무/학사\n\n- 항목\n\t- 탭 들여쓰기 하위 항목\n\n[[다른 노트]]\n"
TABLE_GLUED = "# 제목\n\n| a | b |\n|---|---|\n| 1 | 2 |\n※ 표 바로 뒤 문장\n"


def run_hook(rel_path: str, body: str, with_config: bool = True, env: dict | None = None) -> str:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        if with_config:
            shutil.copy(CONFIG, root / CONFIG.name)
        note = root / rel_path
        note.parent.mkdir(parents=True, exist_ok=True)
        note.write_text(body, encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(HOOK)],
            input=json.dumps({"tool_input": {"file_path": str(note)}}),
            text=True, encoding="utf-8", capture_output=True, check=True,
            env={**(env if env is not None else os.environ), "CLAUDE_PROJECT_DIR": str(root)},
        )
    if not result.stdout.strip():
        return ""
    return json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]


@unittest.skipUnless(shutil.which("node") and shutil.which("npm"), "node/npm not available")
class MarkdownlintHookTest(unittest.TestCase):
    def test_obsidian_syntax_is_clean(self):
        # line-start #tags, tab-indented lists and wikilinks must not warn
        self.assertEqual(run_hook("10_Areas/학사/노트.md", CLEAN), "")

    def test_text_glued_under_table_warns(self):
        # GFM absorbs the glued line as a 1-cell row -> MD056, not MD058
        msg = run_hook("10_Areas/학사/노트.md", TABLE_GLUED)
        self.assertIn("MD056", msg)
        self.assertIn("노트.md", msg)

    def test_ignored_folder_is_silent(self):
        self.assertEqual(run_hook("90_Archive/학사/노트.md", TABLE_GLUED), "")

    def test_no_config_is_silent(self):
        self.assertEqual(run_hook("10_Areas/학사/노트.md", TABLE_GLUED, with_config=False), "")

    def test_non_markdown_is_silent(self):
        self.assertEqual(run_hook("10_Areas/학사/a.txt", TABLE_GLUED), "")

    def test_existing_empty_cache_dir_is_filled(self):
        # a pre-created (empty) cache directory must not make the install look failed
        with tempfile.TemporaryDirectory() as cache:
            env = {**os.environ, "MARKDOWNLINT_CACHE_DIR": cache}
            self.assertIn("MD056", run_hook("10_Areas/학사/노트.md", TABLE_GLUED, env=env))

    def test_missing_install_without_npm_is_silent(self):
        # empty cache + no node/npm on PATH: skip quietly, never fail the write
        with tempfile.TemporaryDirectory() as cache:
            env = {**os.environ, "PATH": "", "MARKDOWNLINT_CACHE_DIR": str(Path(cache) / "none")}
            self.assertEqual(run_hook("10_Areas/학사/노트.md", TABLE_GLUED, env=env), "")


if __name__ == "__main__":
    unittest.main()
