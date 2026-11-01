#!/usr/bin/env python3
"""Regression tests for deliverable-review Step 3 verdict rule.

Run:  python3 -m pytest .claude/skills/deliverable-review/tests/ -q
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
import pytest

HERE = Path(__file__).resolve()
SCRIPTS = HERE.parents[1] / "scripts"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


cv = _load("dr_verdict", SCRIPTS / "check_verdict.py")


def test_unfulfilled_single_returns_unfit():
    findings = [{"id": "A-1", "status": "unfulfilled"}]
    assert cv.decide_verdict(findings) == "검수 부적합"


def test_wording_only_returns_fixable():
    findings = [{"id": "B-1", "status": "wording_only"}]
    assert cv.decide_verdict(findings) == "정정 요청 후 검수 가능"


def test_empty_findings_returns_fit():
    assert cv.decide_verdict([]) == "검수 적합"


@pytest.mark.parametrize("status", ["unproven", "pending_inspection"])
def test_unverified_items_block_acceptance_even_with_only_wording_findings(status):
    assert cv.decide_verdict([
        {"id": "B-1", "status": "wording_only"},
        {"id": "E-1", "status": status},
    ]) == "검수 판단 보류"


def test_confirmed_items_and_unfulfilled_precedence():
    assert cv.decide_verdict([{"id": "D-1", "status": "confirmed"}]) == "검수 적합"
    assert cv.decide_verdict([
        {"id": "A-1", "status": "unfulfilled"},
        {"id": "E-1", "status": "pending_inspection"},
    ]) == "검수 부적합"


@pytest.mark.parametrize("finding", [
    {}, {"id": "A-1"}, {"status": "confirmed"},
    {"id": " ", "status": "confirmed"}, {"id": "A-1", "status": "unknown"},
    {"id": "A-1", "status": []},
    {"id": "A-1", "unfulfilled": False, "wording_only": False},
])
def test_incomplete_or_legacy_input_is_not_silently_accepted(finding):
    with pytest.raises(ValueError):
        cv.decide_verdict([{"id": "A-0", "status": "unfulfilled"}, finding])
