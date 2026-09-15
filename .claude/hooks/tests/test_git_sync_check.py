#!/usr/bin/env python3
"""Regression tests for the SessionStart git-sync hook.

Simulates two machines sharing one origin, where the working tree reaches the
second machine by file copy (Syncthing) instead of git.

Run with: python3 .claude/hooks/tests/test_git_sync_check.py
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
HOOK = HERE.parents[1] / "git-sync-check.py"
GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com",
}


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, env=GIT_ENV, capture_output=True, text=True, check=True
    ).stdout.strip()


def commit_file(repo: Path, name: str, text: str, message: str) -> None:
    (repo / name).write_text(text, encoding="utf-8")
    git(repo, "add", name)
    git(repo, "commit", "-q", "-m", message)


def run_hook(repo: Path) -> str:
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input="{}",
        text=True,
        capture_output=True,
        check=True,
        env={**GIT_ENV, "CLAUDE_PROJECT_DIR": str(repo)},
    )
    if not result.stdout.strip():
        return ""
    return json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]


class GitSyncHookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.origin = self.tmp / "origin.git"
        git(self.tmp, "init", "-q", "--bare", "-b", "main", str(self.origin))
        self.here = self.clone("here")
        commit_file(self.here, "a.md", "v1\n", "init")
        git(self.here, "push", "-q", "origin", "main")
        self.other = self.clone("other")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def clone(self, name: str) -> Path:
        path = self.tmp / name
        git(self.tmp, "clone", "-q", str(self.origin), str(path))
        return path

    def push_from_other_and_sync_files(self) -> None:
        commit_file(self.other, "a.md", "v2\n", "other edit")
        git(self.other, "push", "-q", "origin", "main")
        shutil.copyfile(self.other / "a.md", self.here / "a.md")

    def test_in_sync_is_silent(self) -> None:
        self.assertEqual(run_hook(self.here), "")

    def test_behind_resets_mixed_and_keeps_files(self) -> None:
        self.push_from_other_and_sync_files()
        message = run_hook(self.here)
        self.assertIn("reset --mixed", message)
        self.assertEqual(git(self.here, "rev-parse", "HEAD"), git(self.here, "rev-parse", "origin/main"))
        self.assertEqual(git(self.here, "status", "--porcelain"), "")
        self.assertEqual((self.here / "a.md").read_text(encoding="utf-8"), "v2\n")

    def test_behind_lists_files_that_differ_from_remote(self) -> None:
        self.push_from_other_and_sync_files()
        (self.here / "a.md").write_text("local draft\n", encoding="utf-8")
        message = run_hook(self.here)
        self.assertIn("a.md", message)
        self.assertEqual((self.here / "a.md").read_text(encoding="utf-8"), "local draft\n")

    def test_behind_with_staged_changes_does_not_reset(self) -> None:
        before = git(self.here, "rev-parse", "HEAD")
        self.push_from_other_and_sync_files()
        git(self.here, "add", "a.md")
        message = run_hook(self.here)
        self.assertIn("스테이징", message)
        self.assertEqual(git(self.here, "rev-parse", "HEAD"), before)

    def test_diverged_warns_without_reset(self) -> None:
        self.push_from_other_and_sync_files()
        commit_file(self.here, "b.md", "local\n", "local commit")
        before = git(self.here, "rev-parse", "HEAD")
        message = run_hook(self.here)
        self.assertIn("갈라짐", message)
        self.assertEqual(git(self.here, "rev-parse", "HEAD"), before)

    def test_other_branch_is_silent(self) -> None:
        self.push_from_other_and_sync_files()
        git(self.here, "checkout", "-q", "-b", "feat/x")
        self.assertEqual(run_hook(self.here), "")

    def test_fetch_failure_warns(self) -> None:
        git(self.here, "remote", "set-url", "origin", str(self.tmp / "missing.git"))
        self.assertIn("fetch 실패", run_hook(self.here))

    def test_non_repo_is_silent(self) -> None:
        plain = self.tmp / "plain"
        plain.mkdir()
        self.assertEqual(run_hook(plain), "")


if __name__ == "__main__":
    unittest.main()
