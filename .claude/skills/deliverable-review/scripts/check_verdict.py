#!/usr/bin/env python3
"""Derive a verdict from reviewed requirements and outstanding inspection items."""
from __future__ import annotations


def decide_verdict(findings: list[dict]) -> str:
    """Validate every {id, status} before applying verdict precedence.

    Statuses: confirmed, unfulfilled, wording_only, unproven, pending_inspection.
    An empty list means the caller has completed all checks without findings;
    outstanding evidence or inspections must be supplied explicitly.
    """
    allowed = {"confirmed", "unfulfilled", "wording_only", "unproven", "pending_inspection"}
    if not isinstance(findings, list):
        raise ValueError("findings must be a list")
    statuses = set()
    for index, finding in enumerate(findings):
        if not isinstance(finding, dict):
            raise ValueError(f"finding {index}: expected an object")
        if not isinstance(finding.get("id"), str) or not finding["id"].strip():
            raise ValueError(f"finding {index}: nonempty id is required")
        status = finding.get("status")
        if not isinstance(status, str) or status not in allowed:
            raise ValueError(f"finding {finding['id']}: invalid or missing status")
        statuses.add(status)
    if "unfulfilled" in statuses:
        return "검수 부적합"
    if statuses & {"unproven", "pending_inspection"}:
        return "검수 판단 보류"
    if "wording_only" in statuses:
        return "정정 요청 후 검수 가능"
    return "검수 적합"
