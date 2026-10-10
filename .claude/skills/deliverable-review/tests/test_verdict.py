#!/usr/bin/env python3
"""Regression tests for deliverable-review Step 3 verdict rule.

Run:  python3 -m pytest .claude/skills/deliverable-review/tests/ -q
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

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
    findings = [{"id": "A-1", "unfulfilled": True, "wording_only": False}]
    assert cv.decide_verdict(findings) == "검수 부적합"


def test_wording_only_returns_fixable():
    findings = [{"id": "A-1", "unfulfilled": False, "wording_only": True}]
    assert cv.decide_verdict(findings) == "정정 요청 후 검수 가능"


def test_empty_findings_returns_fixable():
    assert cv.decide_verdict([]) == "정정 요청 후 검수 가능"
