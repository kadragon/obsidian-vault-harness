#!/usr/bin/env python3
"""List active Markdown notes using only their leading frontmatter.

Missing area directories are reported and skipped. No matches is success;
unreadable files/directories or an invalid vault root are errors (exit 1).
"""
from __future__ import annotations

import argparse
from datetime import date, timedelta
import json
import os
from pathlib import Path
import re
import sys

AREAS = {
    "12_Projects": {"open", "active", "in-progress"},
    "10_Areas": {"open", "active", "in-progress"},
    "14_Changes": {"open", "in-progress"},
}
FRONTMATTER = re.compile(r"\A---[ \t]*\n(.*?)^---[ \t]*$", re.MULTILINE | re.DOTALL)
STATUS = re.compile(
    r"^status:[ \t]*(?:'([^'\n]*)'|\"([^\"\n]*)\"|([^\s#'\"]+))"
    r"[ \t]*(?:#.*)?$", re.MULTILINE,
)
GENERATED = re.compile(r"^<!-- homepage-collect:begin v1 -->$", re.MULTILINE)
TASK = re.compile(r"^\s*[-*+]\s+\[([ xX])\]\s*(.*)$")
DATE = re.compile(r"(?<!\d)(\d{4})(?:-(\d{2})-(\d{2})|\.[ \t]*(\d{1,2})\.[ \t]*(\d{1,2})\.?)(?!\d)")
TASK_SECTIONS = {"할 일", "주요 일정", "Todo"}
CONTEXT_SECTIONS = {"현황", "수정 사유", "발생 정보"}
WEEKDAYS = "월화수목금토일"


def active_status(text: str) -> str | None:
    frontmatter = FRONTMATTER.match(text)
    if frontmatter is None:
        return None
    match = STATUS.search(frontmatter.group(1))
    return next((value for value in match.groups() if value is not None), None) if match else None


def raise_walk_error(error: OSError) -> None:
    raise error


def collect(vault: Path) -> dict[str, list[Path]]:
    if not vault.is_dir():
        raise ValueError(f"Vault directory does not exist: {vault}")
    result: dict[str, list[Path]] = {}
    for area, statuses in AREAS.items():
        directory = vault / area
        result[area] = []
        if not directory.exists():
            print(f"WARNING: missing directory, skipped: {directory}", file=sys.stderr)
            continue
        if not directory.is_dir():
            raise ValueError(f"Expected directory: {directory}")
        for parent, dirs, files in os.walk(directory, onerror=raise_walk_error):
            dirs.sort()
            for filename in sorted(files):
                path = Path(parent) / filename
                if path.suffix.lower() != ".md":
                    continue
                text = path.read_text(encoding="utf-8-sig")
                if active_status(text) not in statuses:
                    continue
                if area == "12_Projects" and GENERATED.search(text):
                    continue
                result[area].append(path)
    return result


def date_info(value: date) -> dict:
    weekday = WEEKDAYS[value.weekday()]
    return {"date": value.isoformat(), "weekday": weekday,
            "display": f"{value.month}. {value.day}.({weekday})"}


def dates_in(text: str) -> tuple[list[dict], list[str]]:
    dates, invalid = [], []
    for match in DATE.finditer(text):
        year, month, day, dotted_month, dotted_day = match.groups()
        try:
            value = date(int(year), int(month or dotted_month), int(day or dotted_day))
        except ValueError:
            invalid.append(match.group())
        else:
            dates.append({**date_info(value), "raw": match.group()})
    return dates, invalid


def markdown_lines(text: str):
    """Yield visible lines with original numbers; ignore frontmatter and fenced examples."""
    fm = FRONTMATTER.match(text)
    fm_end = text[:fm.end()].count("\n") + 1 if fm else 0
    fence = None
    section = ""
    for number, raw in enumerate(text.splitlines(), 1):
        if number <= fm_end:
            continue
        line = re.sub(r"^\s*(?:>\s*)+", "", raw)
        marker = re.match(r"^\s*(`{3,}|~{3,})(.*)$", line)
        if marker:
            run, tail = marker.groups()
            if fence is None:
                fence = run
            elif run[0] == fence[0] and len(run) >= len(fence) and not tail.strip():
                fence = None
            continue
        if fence is not None:
            continue
        heading = re.match(r"^##\s+(.+?)\s*#*\s*$", line)
        if heading:
            section = re.sub(r"^[^\w가-힣]+", "", heading.group(1)).strip()
        yield number, raw, line, section


def extract_note(path: Path, area: str, vault: Path, start: date, end: date) -> dict:
    text = path.read_text(encoding="utf-8-sig")
    visible = list(markdown_lines(text))
    title = next((line[2][2:].strip() for line in visible if line[2].startswith("# ")), path.stem)
    project_name = None
    if area == "12_Projects":
        parts = path.relative_to(vault / area).parts
        index = 1 if re.fullmatch(r"\d{4}", parts[0]) else 0
        if len(parts) > index + 1:
            project_name = parts[index]
    tasks, context, departments = [], [], []
    completed = 0
    reasons = set()
    fm = FRONTMATTER.match(text)
    department_lines = [(i, raw) for i, raw in enumerate(text[:fm.end()].splitlines(), 1)] if fm else []
    department_lines += [(number, raw) for number, raw, _, _ in visible]
    for number, raw in department_lines:
        for match in re.finditer(r"#부서/([^\s/#\]\[\"',]+)", raw):
            departments.append({"name": match.group(1), "line": number, "raw": raw})
    for number, raw, line, section in visible:
        task = TASK.match(line)
        if task:
            checked, body = task.groups()
            if checked.lower() == "x":
                completed += 1
                continue
            due_match = re.search(r"📅\s*(\S+)", body)
            due_raw = due_match.group(1) if due_match else None
            due = None
            if due_raw and re.fullmatch(r"\d{4}-\d{2}-\d{2}", due_raw):
                try:
                    due = date.fromisoformat(due_raw)
                except ValueError:
                    pass
            reason = ("invalid_due_date" if due_raw and due is None else "no_due_date")
            if due is not None:
                reason = "due_in_period" if start <= due <= end else "overdue" if due < start else "due_after_period"
            reasons.add(reason)
            review = [reason] if reason != "due_in_period" else []
            if section not in TASK_SECTIONS:
                review.append("outside_task_section")
            tasks.append({"line": number, "raw": raw, "text": body, "section": section,
                          "due": date_info(due) if due else None, "due_raw": due_raw,
                          "candidate_reason": reason, "review_required": review})
        elif section in CONTEXT_SECTIONS and line.strip() and not line.startswith(("#", "[!")):
            dates, invalid = dates_in(line)
            in_period = any(start.isoformat() <= item["date"] <= end.isoformat() for item in dates)
            if in_period:
                reasons.add("context_event_in_period")
            context.append({"line": number, "raw": raw, "text": line, "section": section,
                            "dates": dates, "invalid_dates": invalid, "event_in_period": in_period})
    tasks.sort(key=lambda item: (item["due"]["date"] if item["due"] else "9999-99-99", item["line"]))
    return {"path": str(path), "area": area, "title": title, "project_name": project_name,
            "status": active_status(text), "departments": departments, "context": context,
            "tasks": tasks, "completed_task_count": completed,
            "candidate_reasons": sorted(reasons),
            "review_required": (["no_open_tasks"] if not tasks else [])
                + sorted({reason for task in tasks for reason in task["review_required"]})}


def structured_report(notes: dict[str, list[Path]], vault: Path, reference: date, weeks: int) -> dict:
    start = reference - timedelta(days=reference.weekday())
    end = start + timedelta(days=7 * weeks - 1)
    return {"reference_date": reference.isoformat(), "weeks": weeks,
            "period": {"start": date_info(start), "end": date_info(end)},
            "notes": [extract_note(path, area, vault, start, end)
                      for area, paths in notes.items() for path in paths]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vault", type=Path, nargs="?", default=Path("."))
    parser.add_argument("--json", action="store_true", help="Extract tasks and context with source line numbers")
    parser.add_argument("--weeks", type=int, choices=(1, 2), default=1)
    parser.add_argument("--date", type=date.fromisoformat, default=date.today(), help="Reference date (YYYY-MM-DD)")
    args = parser.parse_args()
    try:
        notes = collect(args.vault)
        report = structured_report(notes, args.vault, args.date, args.weeks) if args.json else None
    except (OSError, UnicodeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    if report is not None:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    for area, paths in notes.items():
        print(f"=== {area} ===")
        for path in paths:
            print(path)
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    sys.exit(main())
