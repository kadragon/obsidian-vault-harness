#!/usr/bin/env python3
"""Record confirmed dispatch facts in an existing note; dry-run by default."""
from __future__ import annotations

import argparse
from datetime import date
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile

MARKER = re.compile(r"<!-- dispatch-record event_id=([A-Za-z0-9_.-]+) sha256=([a-f0-9]{64}) -->")


def one_line(value, name):
    if not isinstance(value, str) or not value.strip() or any(c in value for c in "\r\n\x00"):
        raise ValueError(f"{name} must be a nonempty single line")
    return value


def iso_date(value, name):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError(f"{name} must be YYYY-MM-DD")
    date.fromisoformat(value)
    return value


def validate(record):
    if not isinstance(record, dict):
        raise ValueError("Record must be an object")
    allowed = {"event_id", "note", "dispatched_on", "recorded_on", "summary", "task_line",
               "task_text", "follow_up", "task_heading", "status_heading"}
    if set(record) - allowed:
        raise ValueError(f"Unknown fields: {sorted(set(record) - allowed)}")
    result = dict(record)
    for key in ("event_id", "note", "summary"):
        one_line(result.get(key), key)
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", result["event_id"]):
        raise ValueError("event_id must contain 1-80 ASCII letters, digits, dots, underscores or hyphens")
    for key in ("dispatched_on", "recorded_on"):
        iso_date(result.get(key), key)
    if ("task_line" in result) == ("task_text" in result):
        raise ValueError("Provide exactly one of task_line or task_text")
    one_line(result.get("task_line", result.get("task_text")), "task_line/task_text")
    for key, default in (("task_heading", "## 할 일"), ("status_heading", "## 현황")):
        result.setdefault(key, default)
        if not re.fullmatch(r"##[ \t]+\S.*", one_line(result[key], key)):
            raise ValueError(f"{key} must be an exact level-2 heading")
    if result["task_heading"] == result["status_heading"]:
        raise ValueError("Task and status headings must differ")
    if "follow_up" in result:
        follow = result["follow_up"]
        if not isinstance(follow, dict) or set(follow) - {"text", "due"}:
            raise ValueError("follow_up accepts only text and optional due")
        one_line(follow.get("text"), "follow_up.text")
        if "due" in follow:
            iso_date(follow["due"], "follow_up.due")
    return result


def target_path(vault, note):
    relative = Path(note)
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise ValueError("note must be a vault-relative path without '..'")
    if relative.parts[0].casefold() == "90_archive" or relative.suffix.lower() != ".md":
        raise ValueError("Only existing Markdown notes outside 90_Archive are allowed")
    candidate = vault
    for part in relative.parts:
        candidate = candidate / part
        if candidate.is_symlink():
            raise ValueError("Symlink note paths are not allowed")
    if not candidate.resolve().is_relative_to(vault) or not candidate.is_file():
        raise ValueError("Target must be an existing note inside the vault")
    return candidate


def visible_lines(text):
    """Keep offsets and line endings while excluding YAML and fenced examples."""
    rows = []
    offset, fence = 0, None
    frontmatter = text.lstrip("\ufeff").startswith("---\n") or text.lstrip("\ufeff").startswith("---\r\n")
    for number, raw in enumerate(text.splitlines(keepends=True)):
        body = raw.rstrip("\r\n")
        plain = re.sub(r"^\s*(?:>\s*)+", "", body.lstrip("\ufeff"))
        visible = not frontmatter
        if frontmatter and number > 0 and body.strip() == "---":
            frontmatter = False
        marker = re.match(r"^\s*(`{3,}|~{3,})(.*)$", plain)
        if marker and visible:
            run, tail = marker.groups()
            if fence is None:
                fence = run
            elif run[0] == fence[0] and len(run) >= len(fence) and not tail.strip():
                fence = None
            visible = False
        elif fence is not None:
            visible = False
        rows.append({"start": offset, "end": offset + len(raw), "raw": raw,
                     "body": body, "plain": plain, "visible": visible})
        offset += len(raw)
    if frontmatter or fence is not None:
        raise ValueError("Unclosed frontmatter or fenced block; no changes applied")
    return rows


def section(rows, heading):
    matches = [i for i, row in enumerate(rows) if row["visible"] and row["plain"].rstrip() == heading]
    if len(matches) != 1:
        raise ValueError(f"Expected one heading: {heading}; found {len(matches)}")
    start = matches[0]
    end = next((i for i in range(start + 1, len(rows))
                if rows[i]["visible"] and re.match(r"^#{1,2}\s", rows[i]["plain"])), len(rows))
    return start, end


def append_edit(text, rows, span, lines, newline):
    start, end = span
    callouts = [i for i in range(start + 1, end)
                if rows[i]["visible"] and re.match(r"^\s*>\s*\[!", rows[i]["body"])]
    if len(callouts) > 1:
        raise ValueError("Multiple callouts in target section; choose a more specific note layout")
    prefix = ""
    if callouts:
        last = callouts[0]
        while last + 1 < end and re.match(r"^\s*>", rows[last + 1]["body"]):
            last += 1
        prefix = "> "
    else:
        last = end - 1
        while last > start and not rows[last]["body"].strip():
            last -= 1
    offset = rows[last]["end"]
    separator = "" if offset == 0 or text[offset - 1] in "\r\n" else newline
    return offset, offset, separator + newline.join(prefix + line for line in lines) + newline


def render(text, record):
    digest = hashlib.sha256(json.dumps(record, ensure_ascii=False, sort_keys=True,
                                       separators=(",", ":")).encode("utf-8")).hexdigest()
    rows = visible_lines(text)
    existing = [match.group(2) for row in rows if row["visible"]
                for match in MARKER.finditer(row["plain"]) if match.group(1) == record["event_id"]]
    if existing:
        if existing != [digest]:
            raise ValueError("event_id already exists with a different payload or duplicate markers")
        return text
    task_span = section(rows, record["task_heading"])
    status_span = section(rows, record["status_heading"])
    newline = "\r\n" if "\r\n" in text else "\n"
    edits, additions = [], []
    if "task_line" in record:
        matches = [row for row in rows[task_span[0] + 1:task_span[1]]
                   if row["visible"] and row["body"] == record["task_line"]]
        if len(matches) != 1:
            raise ValueError(f"task_line must match exactly one visible task; found {len(matches)}")
        row = matches[0]
        if not re.match(r"^\s*(?:>\s*)*[-*+]\s+\[ \]\s*", row["body"]) or "✅" in row["body"]:
            raise ValueError("task_line must be an unchecked task without an existing completion date")
        updated = row["body"].replace("[ ]", "[x]", 1) + " ✅ " + record["dispatched_on"]
        edits.append((row["start"], row["start"] + len(row["body"]), updated))
    else:
        additions.append(f"- [x] {record['task_text']} ➕ {record['recorded_on']} ✅ {record['dispatched_on']}")
    if "follow_up" in record:
        follow = record["follow_up"]
        additions.append(f"- [ ] {follow['text']} ➕ {record['recorded_on']}"
                         + (f" 📅 {follow['due']}" if "due" in follow else ""))
    if additions:
        edits.append(append_edit(text, rows, task_span, additions, newline))
    marker = f"<!-- dispatch-record event_id={record['event_id']} sha256={digest} -->"
    edits.append(append_edit(text, rows, status_span,
                             [f"- {record['dispatched_on']} {record['summary']}", marker], newline))
    for start, end, replacement in sorted(edits, reverse=True):
        text = text[:start] + replacement + text[end:]
    return text


def atomic_write(path, original, updated, vault, note):
    mode = stat.S_IMODE(path.stat().st_mode)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".dispatch-", delete=False) as file:
            temporary = Path(file.name)
            file.write(updated)
            file.flush()
            os.fsync(file.fileno())
        os.chmod(temporary, mode)
        if target_path(vault, note) != path or hashlib.sha256(path.read_bytes()).digest() != hashlib.sha256(original).digest():
            raise ValueError("Source changed after read; no changes applied")
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", type=Path, help="Confirmed dispatch record JSON")
    parser.add_argument("--vault", type=Path, default=Path.cwd())
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        record = validate(json.loads(args.record.read_text(encoding="utf-8-sig")))
        vault = args.vault.resolve()
        path = target_path(vault, record["note"])
        original = path.read_bytes()
        text = original.decode("utf-8")
        updated = render(text, record)
        if updated == text:
            print("UNCHANGED: event already recorded")
            return 0
        print("".join(difflib.unified_diff(text.splitlines(keepends=True), updated.splitlines(keepends=True),
                                         fromfile=record["note"], tofile=record["note"])), end="")
        if args.apply:
            atomic_write(path, original, updated.encode("utf-8"), vault, record["note"])
            print("APPLIED")
        else:
            print("DRY RUN: no changes applied")
        return 0
    except (OSError, ValueError, TypeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    sys.exit(main())
