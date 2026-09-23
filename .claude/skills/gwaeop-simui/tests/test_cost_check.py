#!/usr/bin/env python3
"""Regression tests for cost_check.py review-type classification.

Run directly: ``python3 .claude/skills/gwaeop-simui/tests/test_cost_check.py`` must exit 0.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve()
SCRIPT = HERE.parent.parent / "scripts" / "cost_check.py"
spec = importlib.util.spec_from_file_location("cost_check", SCRIPT)
assert spec and spec.loader
cost_check = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = cost_check
spec.loader.exec_module(cost_check)


def run(*argv: str) -> str:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        cost_check.main(list(argv))
    return buf.getvalue()


class MaintTmpTests(unittest.TestCase):
    """가이드 PartⅣ 2.1.6 적용사례(p.191): TMP 45 → 요율 12.25% → 31,865,302원."""

    def test_tmp_from_levels_matches_guide_example(self):
        self.assertEqual(cost_check.tmp_from_levels("보통,보통,보통,단순,보통"), 45)

    def test_tmp_rate_formula(self):
        self.assertAlmostEqual(cost_check.maint_rate_for(0), 0.10)
        self.assertAlmostEqual(cost_check.maint_rate_for(45), 0.1225)
        self.assertAlmostEqual(cost_check.maint_rate_for(100), 0.15)

    def test_maint_with_tmp_reproduces_guide_amount(self):
        out = run("maint", "--dev-amount", "249222058", "--maint-amount", "31865302",
                  "--months", "12", "--tmp-levels", "보통,보통,보통,단순,보통",
                  "--direct-expense", "1335600")
        self.assertIn("12.25%", out)
        self.assertIn("31,865,302원", out)
        self.assertIn("TMP 산정액과 일치", out)

    def test_rejects_unknown_level(self):
        with self.assertRaises(ValueError):
            cost_check.tmp_from_levels("보통,보통,보통,단순")


class CommercialMaintTests(unittest.TestCase):
    """가이드 PartⅣ 2.2.6 적용사례(p.199): 3등급 16% × 50,000,000 = 8,000,000원."""

    def test_grade_rates(self):
        self.assertEqual(cost_check.COMMERCIAL_MAINT_RATES,
                         {1: 0.20, 2: 0.18, 3: 0.16, 4: 0.14, 5: 0.12})

    def test_commercial_reproduces_guide_amount(self):
        out = run("commercial", "--license-amount", "50000000", "--grade", "3")
        self.assertIn("8,000,000원", out)

    def test_commercial_flags_overcharge(self):
        out = run("commercial", "--license-amount", "50000000", "--grade", "3",
                  "--maint-amount", "10000000")
        self.assertIn("과다", out)


if __name__ == "__main__":
    unittest.main()
