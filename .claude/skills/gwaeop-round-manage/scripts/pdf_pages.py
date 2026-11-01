#!/usr/bin/env python3
"""Split/merge PDFs from an approved 1-based page manifest; dry-run by default."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path, PurePosixPath

from pypdf import PdfReader, PdfWriter


class PlanError(ValueError):
    """The entire plan must be corrected before any output is written."""


def ranges(value, count: int, label: str) -> list[int]:
    if not isinstance(value, list) or not value:
        raise PlanError(f"{label}: pages must be a nonempty list of [first, last] ranges")
    result = []
    for pair in value:
        if (not isinstance(pair, list) or len(pair) != 2
                or any(type(n) is not int for n in pair)):
            raise PlanError(f"{label}: each range must contain two integers")
        first, last = pair
        if first < 1 or last < first or last > count:
            raise PlanError(f"{label}: range {pair} outside 1..{count} or reversed")
        result.extend(range(first, last + 1))
    return result


def output_path(root: Path, value) -> tuple[str, Path]:
    if not isinstance(value, str) or not value:
        raise PlanError("output path must be a nonempty relative PDF path")
    path = PurePosixPath(value)
    # Check raw components as PurePath collapses '.' and empty components.
    pieces = value.split("/")
    reserved = re.compile(r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)", re.I)
    if (path.is_absolute() or any(p in {"", ".", ".."} for p in pieces)
            or any(re.search(r'[\\<>:"|?*\x00-\x1f\x7f]', p) for p in pieces)
            or any(p.endswith((" ", ".")) or reserved.match(p) for p in pieces)
            or path.suffix.lower() != ".pdf"):
        raise PlanError(f"invalid output path: {value}")
    target = root.joinpath(*pieces)
    if not target.resolve().is_relative_to(root):
        raise PlanError(f"output escapes output root: {value}")
    if target.exists() or target.is_symlink():
        raise PlanError(f"output already exists: {value}")
    for parent in target.parents:
        if parent.exists() and not parent.is_dir():
            raise PlanError(f"output parent is not a directory: {parent}")
        if parent == root:
            break
    return value, target


def preflight(manifest_path: Path, root: Path) -> tuple[dict, dict, list]:
    config = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if not isinstance(config, dict) or type(config.get("version")) is not int or config["version"] != 1:
        raise PlanError("manifest version must be 1")
    for key in ("allow_unused_pages", "allow_reuse"):
        if type(config.get(key, False)) is not bool:
            raise PlanError(f"{key} must be boolean")
    sources = config.get("sources")
    outputs = config.get("outputs")
    if not isinstance(sources, dict) or not sources:
        raise PlanError("sources must be a nonempty object")
    if not isinstance(outputs, list) or not outputs:
        raise PlanError("outputs must be a nonempty list")
    loaded, source_reports, source_paths = {}, {}, set()
    for alias, value in sources.items():
        if not isinstance(alias, str) or not alias.strip() or not isinstance(value, str) or not value:
            raise PlanError("source aliases and paths must be nonempty strings")
        path = (manifest_path.parent / value).resolve()
        if path in source_paths:
            raise PlanError(f"source declared under multiple aliases: {path}")
        source_paths.add(path)
        data = path.read_bytes()
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise PlanError(f"encrypted source is unsupported: {alias}")
        if not reader.pages:
            raise PlanError(f"source has no pages: {alias}")
        loaded[alias] = reader
        source_reports[alias] = {
            "path": str(path), "pages": len(reader.pages),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
    plan, names, usage = [], set(), Counter()
    for output in outputs:
        if not isinstance(output, dict):
            raise PlanError("each output must be an object")
        name, target = output_path(root, output.get("path"))
        key = unicodedata.normalize("NFC", name).casefold()
        if key in names or any(key.startswith(n + "/") or n.startswith(key + "/") for n in names):
            raise PlanError(f"duplicate or conflicting output path: {name}")
        names.add(key)
        parts = output.get("parts")
        if not isinstance(parts, list) or not parts:
            raise PlanError(f"{name}: parts must be nonempty")
        pages, seen = [], set()
        for part in parts:
            if not isinstance(part, dict) or not isinstance(part.get("source"), str):
                raise PlanError(f"{name}: each part needs a source alias")
            alias = part["source"]
            if alias not in loaded:
                raise PlanError(f"{name}: unknown source {alias}")
            for page in ranges(part.get("pages"), len(loaded[alias].pages), name):
                pair = (alias, page)
                if pair in seen:
                    raise PlanError(f"{name}: page repeated within output: {alias}:{page}")
                seen.add(pair)
                pages.append(pair)
                usage[pair] += 1
        plan.append({"path": name, "target": target, "pages": pages})
    duplicates = [f"{a}:{p}" for (a, p), count in usage.items() if count > 1]
    if duplicates and not config.get("allow_reuse", False):
        raise PlanError(f"pages reused across outputs; set allow_reuse explicitly: {', '.join(duplicates)}")
    for alias, source in source_reports.items():
        unused = [p for p in range(1, source["pages"] + 1) if not usage[(alias, p)]]
        source["unused_pages"] = unused
        if unused and not config.get("allow_unused_pages", False):
            raise PlanError(f"unused pages in {alias}: {unused}; set allow_unused_pages explicitly")
    report = {
        "mode": "dry-run", "ok": True, "sources": source_reports,
        "reused_pages": duplicates,
        "outputs": [{"path": p["path"], "page_count": len(p["pages"]),
                     "page_order": [[a, n] for a, n in p["pages"]]} for p in plan],
        "created": [], "failed": [], "not_written": [],
    }
    return report, loaded, plan


def execute(manifest_path: Path, output_root: Path, apply: bool = False) -> dict:
    root = output_root.resolve()
    try:
        report, loaded, plan = preflight(manifest_path.resolve(), root)
    except Exception as exc:
        return {"ok": False, "mode": "apply" if apply else "dry-run", "errors": [str(exc)],
                "created": [], "failed": [], "not_written": []}
    if not apply:
        return report
    report["mode"] = "apply"
    for index, output in enumerate(plan):
        target = output["target"]
        created = False
        try:
            # Recheck paths before creating directories and never overwrite a raced file.
            output_path(root, output["path"])
            writer = PdfWriter()
            for alias, page in output["pages"]:
                writer.add_page(loaded[alias].pages[page - 1])
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as stream:
                created = True
                writer.write(stream)
            actual = len(PdfReader(target).pages)
            if actual != len(output["pages"]):
                raise PlanError(f"page count mismatch: expected {len(output['pages'])}, got {actual}")
            report["created"].append({"path": output["path"], "page_count": actual})
        except Exception as exc:
            report["ok"] = False
            report["failed"].append({"path": output["path"], "error": str(exc),
                                     "created_unverified": created})
            report["not_written"] = [p["path"] for p in plan[index + 1:]]
            break
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output-root", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="validate only (default)")
    mode.add_argument("--apply", action="store_true", help="write new files after full preflight")
    args = parser.parse_args(argv)
    result = execute(args.manifest, args.output_root, apply=args.apply)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
