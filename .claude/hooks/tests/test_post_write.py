#!/usr/bin/env python3
"""Tests for the consolidated PostToolUse runner (post-write.py) and the tag check.

Run with: python3 .claude/hooks/tests/test_post_write.py

Each test copies .claude/hooks and .claude/lib into a temp directory that acts as the
vault root, because check-tags.py only inspects files under the vault it lives in.
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

CLAUDE = Path(__file__).resolve().parents[2]
FENCE = "```"

BAD_TAGS = (
    "---\ntype: work\nstatus: open\n---\n# 제목\n\n"
    "#부서/학사관리과/행정주사_김영희\n"
    "#업무/{area} is a placeholder\n"
    "`#업무/가짜/인라인` is inline code\n"
    + FENCE + "\n#업무/가짜/펜스\n" + FENCE + "\n"
    "#업무/학사/없는영역/x\n"
    "다음 줄 본문\n"
)
BAD_TODO = "# t\n- [ ] 할일 ➕ 2026-13-45\n"


def run_runner(vault: Path, rel: str, body: str, tool: str = "Edit", write: bool = True) -> str:
    note = vault / rel
    if write:
        note.parent.mkdir(parents=True, exist_ok=True)
        note.write_text(body, encoding="utf-8", newline="")
    result = subprocess.run(
        [sys.executable, str(vault / ".claude" / "hooks" / "post-write.py")],
        input=json.dumps({"tool_name": tool, "tool_input": {"file_path": str(note)}}),
        text=True, encoding="utf-8", capture_output=True,
        env={**os.environ, "CLAUDE_PROJECT_DIR": str(vault)},
    )
    assert result.returncode == 0, result.stderr
    if not result.stdout.strip():
        return ""
    return json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]


class PostWriteTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self._tmp.name)
        for sub in ("hooks", "lib"):
            shutil.copytree(CLAUDE / sub, self.vault / ".claude" / sub,
                            ignore=shutil.ignore_patterns("__pycache__", "tests"))
        (self.vault / "10_Areas" / "학사").mkdir(parents=True)  # registers #업무/학사

    def tearDown(self):
        self._tmp.cleanup()

    def test_clean_note_is_silent(self):
        self.assertEqual(run_runner(self.vault, "10_Areas/학사/n.md",
                                    "---\ntype: work\nstatus: open\n---\n# t\n\n#업무/학사\n\n## 관련\n\n## 할 일\n"), "")

    def test_tag_findings(self):
        msg = run_runner(self.vault, "10_Areas/학사/n.md", BAD_TAGS)
        self.assertIn("[태그 검증 경고] n.md", msg)
        self.assertIn("#부서/학사관리과/행정주사_김영희 → #부서/학사관리과/팀장_김영희", msg)
        self.assertIn("#업무/학사/없는영역/x → #업무/없는영역/x", msg)
        self.assertIn("tag-validator 에이전트를 실행하여 태그를 정규화하세요.", msg)
        # placeholders, inline code and fenced code are not tags
        for ignored in ("{area}", "인라인", "펜스"):
            self.assertNotIn(ignored, msg)

    def test_tag_never_spans_newline(self):
        # a tag at the end of a line must not swallow the next line (grep -o is line based)
        msg = run_runner(self.vault, "10_Areas/학사/n.md", "# t\n#업무/학사/없는영역\n다음 줄\n")
        self.assertIn("#업무/학사/없는영역 → #업무/없는영역", msg)
        self.assertNotIn("다음 줄", msg)

    def test_dept_tag_in_frontmatter_with_crlf(self):
        body = "---\r\ntype: work\r\nstatus: open\r\n#부서/학사관리과\r\n---\r\n# t\r\n#업무/학사\r\n"
        msg = run_runner(self.vault, "10_Areas/학사/n.md", body)
        self.assertIn("#부서 태그가 frontmatter에 있음", msg)

    @unittest.skipUnless(os.name == "nt", "MSYS-style drive paths exist only on Windows")
    def test_msys_style_path_is_accepted(self):
        note = self.vault / "10_Areas/학사/n.md"
        note.parent.mkdir(parents=True, exist_ok=True)
        note.write_text(BAD_TAGS, encoding="utf-8", newline="")
        drive, rest = str(note).split(":", 1)
        msys = "/" + drive.lower() + rest.replace("\\", "/")
        result = subprocess.run(
            [sys.executable, str(self.vault / ".claude" / "hooks" / "check-tags.py")],
            input=json.dumps({"tool_input": {"file_path": msys}}),
            text=True, encoding="utf-8", capture_output=True,
            env={**os.environ, "CLAUDE_PROJECT_DIR": str(self.vault)})
        self.assertIn("[태그 검증 경고]",
                      json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"])

    def test_dept_tag_in_frontmatter(self):
        msg = run_runner(self.vault, "10_Areas/학사/n.md",
                         "---\ntype: work\nstatus: open\n#부서/학사관리과\n---\n# t\n#업무/학사\n")
        self.assertIn("#부서 태그가 frontmatter에 있음 (본문으로 이동 필요)", msg)

    def test_messages_are_combined_in_check_order(self):
        msg = run_runner(self.vault, "10_Areas/학사/n.md", BAD_TODO + BAD_TAGS)
        self.assertIn("[WARNING] 할일 날짜 점검", msg)
        self.assertIn("[태그 검증 경고]", msg)
        self.assertLess(msg.index("[WARNING] 할일"), msg.index("[태그 검증 경고]"))

    def test_folder_rules_run_for_write_only(self):
        rel = "90_Archive/x/a.md"
        self.assertEqual(run_runner(self.vault, rel, "# a\n", tool="Edit"), "")
        self.assertIn("90_Archive/ 에 직접 파일 생성 금지",
                      run_runner(self.vault, rel, "# a\n", tool="Write"))

    def test_non_markdown_and_missing_file_are_silent(self):
        self.assertEqual(run_runner(self.vault, "10_Areas/학사/a.txt", BAD_TAGS), "")
        self.assertEqual(run_runner(self.vault, "10_Areas/학사/none.md", "", write=False), "")

    def test_broken_check_is_reported_and_others_still_run(self):
        # a SyntaxError in a rule library must not turn into "no findings"
        (self.vault / ".claude" / "lib" / "note_rules.py").write_text("def broken(:\n", encoding="utf-8")
        msg = run_runner(self.vault, "10_Areas/학사/n.md", BAD_TODO)
        self.assertIn("[훅 오류] check-template.py: SyntaxError", msg)
        self.assertIn("[WARNING] 할일 날짜 점검", msg)


if __name__ == "__main__":
    unittest.main()
