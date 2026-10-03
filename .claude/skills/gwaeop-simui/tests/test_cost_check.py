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


class ReviewTypeTests(unittest.TestCase):
    def test_basis_is_amount_excluding_vat(self):
        out = run("sum", "--items", "105000000", "--vat-included")
        self.assertIn("부가세 제외", out)
        self.assertIn("간소화 심의 대상", out)

    def test_boundary_band_warns_when_vat_inclusive_exceeds_limit(self):
        # 부가세 포함 1.05억 = 부가세 제외 약 0.95억 — 포함 기준으로 읽으면 정식 심의로 갈린다.
        out = run("sum", "--items", "105000000", "--vat-included")
        self.assertIn("경계", out)

    def test_no_boundary_warning_outside_band(self):
        out = run("sum", "--items", "50000000", "--vat-included")
        self.assertNotIn("경계", out)

    def test_small_contract_band_prints_light_review_tier(self):
        # 추정가격 2천만원 이하 = 1인 견적·예정가격 생략 가능 수의계약 — 경량 검토.
        out = run("sum", "--items", "20000000", "--vat-included")
        self.assertIn("검토 강도: 경량", out)

    def test_above_small_contract_band_is_standard_tier(self):
        out = run("sum", "--items", "66000000", "--vat-included")
        self.assertNotIn("검토 강도: 경량", out)
        self.assertIn("검토 강도: 표준", out)

    def test_over_limit_is_formal_review(self):
        out = run("sum", "--items", "121000000", "--vat-included")
        self.assertIn("정식 심의", out)


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
