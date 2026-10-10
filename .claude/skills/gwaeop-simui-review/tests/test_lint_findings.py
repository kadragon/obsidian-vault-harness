#!/usr/bin/env python3
"""Regression tests for lint_findings.py.

Run directly: ``python3 .claude/skills/gwaeop-simui-review/tests/test_lint_findings.py`` must exit 0.
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve()
SCRIPT = HERE.parent.parent / "scripts" / "lint_findings.py"
spec = importlib.util.spec_from_file_location("lint_findings", SCRIPT)
assert spec and spec.loader
lint_findings = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = lint_findings
spec.loader.exec_module(lint_findings)

NOTE = """## 지적사항

1. **적정 사업기간 산정 주체 부적정** — 「소프트웨어사업 계약 및 관리감독에 관한 지침」 제10조제2항에 따라 과업심의위원회가 산정하여야 하나, 산정표는 발주부서 검토안으로 작성되어 있음.
   요청 — 위원회 산정 결과를 제출 바람
2. **요구사항 상세화 미흡** — 요구사항이 그룹 단위로만 정리돼 바람직하지 않음.
"""


class LintFindingsTests(unittest.TestCase):
    def _lint(self, raw: bytes) -> list[dict]:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "note.md"
            path.write_bytes(raw)
            return lint_findings.lint(path)

    def test_complete_and_incomplete_findings(self):
        results = self._lint(NOTE.encode("utf-8"))
        self.assertEqual([r["missing"] == [] for r in results], [True, False])

    def test_utf8_bom_does_not_hide_findings(self):
        # Windows editors and PowerShell `Set-Content -Encoding utf8` prepend a BOM.
        results = self._lint(b"\xef\xbb\xbf" + NOTE.encode("utf-8"))
        self.assertEqual(len(results), 2)


if __name__ == "__main__":
    unittest.main()
