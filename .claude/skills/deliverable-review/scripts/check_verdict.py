#!/usr/bin/env python3
"""Step 3 verdict rule: any unfinished task in A -> unfit, else fixable."""
from __future__ import annotations


def decide_verdict(findings: list[dict]) -> str:
    """Return '검수 부적합' if any finding has unfulfilled=True, else '정정 요청 후 검수 가능'."""
    for f in findings or []:
        if f.get("unfulfilled"):
            return "검수 부적합"
    return "정정 요청 후 검수 가능"
