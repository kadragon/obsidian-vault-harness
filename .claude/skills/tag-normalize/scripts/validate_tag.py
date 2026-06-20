#!/usr/bin/env python3
"""Validate and normalize `#업무` / `#부서` tags per tag-normalize skill rules.

Usage:
    python validate_tag.py '#업무/학사/수업성적/강좌관리'
    python validate_tag.py --json '#부서/학사관리과/행정주사보_김영희'
    echo '#업무/...' | python validate_tag.py -

Exit codes:
    0 — tag is valid as-is
    1 — tag is invalid; normalized suggestion printed
    2 — unrecoverable (unknown area, malformed)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path


def _discover_allowed_areas() -> set[str] | None:
    """Derive the allowed `#업무/{area}` set at runtime from 10_Areas/ folder names.

    Source of truth: "#업무/ 태그 = 10_Areas 폴더명 그대로" (문서 유형 불문).
    Resolve the vault robustly via $CLAUDE_PROJECT_DIR, else walk up from this
    script's location. Return None if 10_Areas/ cannot be located/read so the
    caller can degrade gracefully (skip the unknown-area check rather than fail).
    """
    candidates: list[Path] = []
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        candidates.append(Path(env) / "10_Areas")
    here = Path(__file__).resolve()
    candidates.extend(parent / "10_Areas" for parent in here.parents)
    for areas in candidates:
        try:
            if areas.is_dir():
                # NFC-normalize: macOS lists filenames in NFD; tags are NFC.
                names = {unicodedata.normalize("NFC", p.name)
                         for p in areas.iterdir() if p.is_dir()}
                if names:
                    return names
        except OSError:
            continue
    return None


# None ⇒ 10_Areas/ unavailable ⇒ unknown-area check is skipped (graceful degrade).
ALLOWED_AREAS = _discover_allowed_areas()

FORBIDDEN_PREFIXES = ("인트라넷/", "부속/", "학사/", "공통/", "시스템/")

# Specific forbidden-prefix rewrites that map to a real area
PREFIX_REWRITES = [
    (re.compile(r"^#업무/공통/시스템/"), "#업무/개발공통/"),
    (re.compile(r"^#업무/인트라넷/학생서비스/공결신청"),
     "#업무/수업성적/출석부관리/공결신청"),
]

# job title -> normalized rank
JOB_TITLE_MAP = {
    "행정서기": "주무관", "행정서기보": "주무관",
    "행정주사보": "주무관", "전산서기보": "주무관",
    "전산주사": "주무관", "사서주사보": "주무관",
    "대학회계직": "주무관", "사무원": "주무관", "한시임기제": "주무관",
    "계약직조교": "조교",
    # 6급 행정주사 → 팀장 (needs context; default to 팀장)
    "행정주사": "팀장",
}

DEPARTMENT_MAP = {
    "대외협력과": "대외협력부",
    "대외협력본부": "대외협력부",
    "일반대학원": "대학원",
    "교육대학원": "대학원",
    "교육정보원": "정보전산원",
    "학총무과": "총무과",
    "입학학생처": "입학인재관리과",
}

SPECIAL_CHAR_RE = re.compile(r"[ &+]")


@dataclass
class Result:
    original: str
    normalized: str
    valid: bool
    issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def normalize_upmu(tag: str) -> Result:
    """Normalize a #업무/... tag."""
    issues: list[str] = []
    normalized = tag.strip()

    # strip forbidden prefixes with known rewrites first
    for pat, repl in PREFIX_REWRITES:
        if pat.match(normalized):
            new = pat.sub(repl, normalized)
            issues.append(f"prefix rewrite → {new}")
            normalized = new
            break

    # strip any remaining single forbidden prefix right after #업무/
    for bad in FORBIDDEN_PREFIXES:
        target = f"#업무/{bad}"
        if normalized.startswith(target):
            normalized = "#업무/" + normalized[len(target):]
            issues.append(f"removed forbidden prefix '{bad.rstrip('/')}'")
            break

    # parentheses → underscores
    if "(" in normalized or ")" in normalized:
        normalized = normalized.replace("(", "_").replace(")", "_")
        issues.append("parentheses → underscores")

    # special chars
    if SPECIAL_CHAR_RE.search(normalized):
        normalized = SPECIAL_CHAR_RE.sub("_", normalized)
        issues.append("space/&/+ replaced with _")

    # check area
    parts = normalized.split("/")
    if len(parts) < 2 or parts[0] != "#업무":
        issues.append("malformed: must start with '#업무/'")
        return Result(tag, normalized, False, issues)

    area = unicodedata.normalize("NFC", parts[1])
    if ALLOWED_AREAS is not None and area not in ALLOWED_AREAS:
        issues.append(f"unknown area '{area}' (not a 10_Areas/ folder)")
        return Result(tag, normalized, False, issues)

    valid = not issues
    return Result(tag, normalized, valid, issues)


def normalize_buseo(tag: str) -> Result:
    """Normalize a #부서/... tag."""
    issues: list[str] = []
    normalized = tag.strip()

    # drop P_ prefix on department
    if re.search(r"#부서/P_", normalized):
        normalized = normalized.replace("/P_", "/")
        issues.append("removed P_ prefix")

    # drop 퇴직/ middle path
    if "/퇴직/" in normalized:
        normalized = normalized.replace("/퇴직/", "/")
        issues.append("removed 퇴직/ middle path")

    parts = normalized.split("/")
    if len(parts) < 3 or parts[0] != "#부서":
        issues.append("malformed: must be '#부서/{부서명}/{직급}_{이름}'")
        return Result(tag, normalized, False, issues)

    # department normalization (position 1 unless 학과 path)
    if parts[1] == "학과":
        pass  # 학과/{학과명}/조교_{이름} stays
    elif re.match(r"제[1-4]대학", parts[1]) and len(parts) >= 4 and "조교" in parts[-1]:
        # 제X대학/{학과명}/조교_X → 학과/{학과명}/조교_X
        issues.append(f"학과 조교는 학과/ 하위로 이동 ({parts[1]} → 학과)")
        parts = ["#부서", "학과"] + parts[2:]
    else:
        dept = parts[1]
        if dept in DEPARTMENT_MAP:
            issues.append(f"부서명 '{dept}' → '{DEPARTMENT_MAP[dept]}'")
            parts[1] = DEPARTMENT_MAP[dept]

    # job-title normalization (last segment: 직급_이름)
    last = parts[-1]
    if "_" in last:
        rank, name = last.split("_", 1)
        if rank in JOB_TITLE_MAP:
            new_rank = JOB_TITLE_MAP[rank]
            issues.append(f"직급 '{rank}' → '{new_rank}'"
                          + (" (팀 직함이 있다면 {업무}팀장으로 수정)"
                             if rank == "행정주사" else ""))
            parts[-1] = f"{new_rank}_{name}"

    normalized = "/".join(parts)
    valid = not issues
    return Result(tag, normalized, valid, issues)


def validate(tag: str) -> Result:
    tag = tag.strip()
    if tag.startswith("#업무"):
        return normalize_upmu(tag)
    if tag.startswith("#부서"):
        return normalize_buseo(tag)
    return Result(tag, tag, False, ["unsupported tag family (expected #업무 or #부서)"])


def _read_input(arg: str) -> list[str]:
    if arg == "-":
        return [ln.strip() for ln in sys.stdin if ln.strip()]
    return [arg]


def main() -> int:
    p = argparse.ArgumentParser(description="Validate/normalize #업무 or #부서 tags.")
    p.add_argument("tag", help="tag string, or '-' to read one-per-line from stdin")
    p.add_argument("--json", action="store_true", help="emit JSON results")
    args = p.parse_args()

    tags = _read_input(args.tag)
    results = [validate(t) for t in tags]

    if args.json:
        print(json.dumps([r.to_dict() for r in results],
                         ensure_ascii=False, indent=2))
    else:
        for r in results:
            status = "OK" if r.valid else "FIX"
            print(f"[{status}] {r.original}")
            if r.original != r.normalized:
                print(f"      → {r.normalized}")
            for issue in r.issues:
                print(f"      - {issue}")

    return 0 if all(r.valid for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
