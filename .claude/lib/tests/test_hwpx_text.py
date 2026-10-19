#!/usr/bin/env python3
"""Tests for the shared HWPX text extraction helper (.claude/lib/hwpx_text.py).

Run directly: ``python3 .claude/lib/tests/test_hwpx_text.py`` must exit 0.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve()
SCRIPT = HERE.parent.parent / "hwpx_text.py"
MARKET = ".claude/plugins/marketplaces/kadragon/prod/skills/hwpx/scripts/text.py"
CACHE = ".claude/plugins/cache/kadragon/prod/{ver}/skills/hwpx/scripts/text.py"
CODEX_CACHE = ".codex/plugins/cache/kadragon/prod/{ver}/skills/hwpx/scripts/text.py"

OK_TOOL = "import sys\nprint('# 제목\\n\\n| 항목 | 값 |')\n"
FAIL_TOOL = "import sys\nsys.stderr.write('bad zip\\n')\nsys.exit(1)\n"


class HwpxTextCliTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name) / "home"
        self.home.mkdir()
        self.src = Path(self._tmp.name) / "공문.hwpx"
        self.src.write_bytes(b"PK\x03\x04")

    def tearDown(self):
        self._tmp.cleanup()

    def _tool(self, rel: str, body: str) -> Path:
        p = self.home / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
        return p

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        env = dict(os.environ, HOME=str(self.home), USERPROFILE=str(self.home), PYTHONIOENCODING="utf-8")
        return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True,
                              text=True, encoding="utf-8", env=env, timeout=60)

    def test_resolves_marketplaces_before_cache(self):
        self._tool(CACHE.format(ver="0.9.0"), FAIL_TOOL)
        self._tool(MARKET, OK_TOOL)
        r = self._run(str(self.src))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("| 항목 | 값 |", r.stdout)

    def test_cache_fallback_writes_out_file(self):
        self._tool(CACHE.format(ver="0.8.0"), FAIL_TOOL)
        self._tool(CACHE.format(ver="0.9.0"), OK_TOOL)
        out = Path(self._tmp.name) / "out.md"
        r = self._run(str(self.src), "--out", str(out))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("# 제목", out.read_text(encoding="utf-8"))

    def test_cache_fallback_sorts_versions_numerically(self):
        self._tool(CACHE.format(ver="0.9.0"), FAIL_TOOL)
        self._tool(CACHE.format(ver="0.10.0"), OK_TOOL)
        r = self._run(str(self.src))
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_codex_only_cache_sorts_versions_numerically(self):
        self._tool(CODEX_CACHE.format(ver="3.9.0"), FAIL_TOOL)
        self._tool(CODEX_CACHE.format(ver="3.10.0"), OK_TOOL)
        out = Path(self._tmp.name) / "codex.md"
        r = self._run(str(self.src), "--out", str(out))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("# 제목", out.read_text(encoding="utf-8"))

    def test_claude_cache_precedes_codex_cache(self):
        self._tool(CACHE.format(ver="0.9.0"), OK_TOOL)
        self._tool(CODEX_CACHE.format(ver="3.10.0"), FAIL_TOOL)
        r = self._run(str(self.src))
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_unwritable_out_is_unverified(self):
        self._tool(MARKET, OK_TOOL)
        r = self._run(str(self.src), "--out", str(Path(self._tmp.name) / "없는폴더" / "x.md"))
        self.assertEqual(r.returncode, 3)
        self.assertIn("UNVERIFIED:", r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_missing_tool_is_unverified_not_exception(self):
        r = self._run(str(self.src))
        self.assertEqual(r.returncode, 3)
        self.assertTrue(r.stderr.startswith("UNVERIFIED:"), r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_extraction_failure_is_unverified(self):
        self._tool(MARKET, FAIL_TOOL)
        r = self._run(str(self.src))
        self.assertEqual(r.returncode, 3)
        self.assertIn("UNVERIFIED:", r.stderr)
        self.assertIn("bad zip", r.stderr)

    def test_legacy_hwp_needs_conversion(self):
        self._tool(MARKET, OK_TOOL)
        hwp = Path(self._tmp.name) / "공문.hwp"
        hwp.write_bytes(b"\xd0\xcf\x11\xe0")
        r = self._run(str(hwp))
        self.assertEqual(r.returncode, 4)
        self.assertTrue(r.stderr.startswith("NEEDS_HWPX:"), r.stderr)

    def test_missing_source_is_unverified(self):
        self._tool(MARKET, OK_TOOL)
        r = self._run(str(Path(self._tmp.name) / "없음.hwpx"))
        self.assertEqual(r.returncode, 3)
        self.assertIn("UNVERIFIED:", r.stderr)


if __name__ == "__main__":
    unittest.main()
