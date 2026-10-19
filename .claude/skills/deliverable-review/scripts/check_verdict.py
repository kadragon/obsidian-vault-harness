#!/usr/bin/env python3
"""Step 3 verdict rule: no A finding -> fit, any unfinished task in A -> unfit, else fixable."""
from __future__ import annotations


def decide_verdict(findings: list[dict]) -> str:
    """Return '검수 적합' with no findings, '검수 부적합' if any is unfulfilled, else '정정 요청 후 검수 가능'."""
    if not findings:
        return "검수 적합"
    for f in findings:
        if f.get("unfulfilled"):
            return "검수 부적합"
    return "정정 요청 후 검수 가능"
