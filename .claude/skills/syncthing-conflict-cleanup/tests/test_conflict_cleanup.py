#!/usr/bin/env python3
"""Regression tests for syncthing-conflict-cleanup/scripts/conflict_cleanup.py.

Run with: pytest .claude/skills/syncthing-conflict-cleanup/tests/test_conflict_cleanup.py
Isolation: every test uses the tmp_path fixture — never touches the real vault.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve()
SCRIPT = HERE.parents[1] / "scripts" / "conflict_cleanup.py"


def _load():
    spec = importlib.util.spec_from_file_location("conflict_cleanup", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["conflict_cleanup"] = mod
    spec.loader.exec_module(mod)
    return mod


cc = _load()

CONFLICT_SUFFIX = ".sync-conflict-20260427-065342-ABC1234"


def make_conflict(root: Path, name: str, body: str) -> Path:
    """Create <root>/<stem><CONFLICT_SUFFIX><ext> with given body."""
    stem, ext = name.rsplit(".", 1)
    conflict = root / f"{stem}{CONFLICT_SUFFIX}.{ext}"
    conflict.write_text(body, encoding="utf-8")
    return conflict


def test_classify_identical(tmp_path):
    orig = tmp_path / "note.md"
    orig.write_text("# hello\n", encoding="utf-8")
    conflict = make_conflict(tmp_path, "note.md", "# hello\n")

    result = cc.classify(conflict)

    assert result["status"] == "identical"
    assert result["original"] == str(orig)


def test_classify_different(tmp_path):
    orig = tmp_path / "note.md"
    orig.write_text("# original\n", encoding="utf-8")
    conflict = make_conflict(tmp_path, "note.md", "# changed\n")

    result = cc.classify(conflict)

    assert result["status"] == "different"
    assert result["original"] == str(orig)


def test_classify_orphan(tmp_path):
    conflict = make_conflict(tmp_path, "gone.md", "# orphan\n")

    result = cc.classify(conflict)

    assert result["status"] == "orphan"
    assert not Path(result["original"]).exists()


def test_purge_dry_run_moves_nothing(tmp_path, capsys):
    orig = tmp_path / "note.md"
    orig.write_text("# same\n", encoding="utf-8")
    conflict = make_conflict(tmp_path, "note.md", "# same\n")

    cc.cmd_purge(SimpleNamespace(root=str(tmp_path), apply=False))

    out = capsys.readouterr().out
    assert "DRY-RUN" in out
    assert conflict.exists()
    assert orig.exists()
    assert not (tmp_path / ".trash").exists()


def test_purge_apply_moves_only_identical(tmp_path):
    same_orig = tmp_path / "same.md"
    same_orig.write_text("# same\n", encoding="utf-8")
    same_conflict = make_conflict(tmp_path, "same.md", "# same\n")

    diff_orig = tmp_path / "diff.md"
    diff_orig.write_text("# v1\n", encoding="utf-8")
    diff_conflict = make_conflict(tmp_path, "diff.md", "# v2\n")

    cc.cmd_purge(SimpleNamespace(root=str(tmp_path), apply=True))

    assert not same_conflict.exists()
    assert same_orig.exists()  # purge never touches the original
    assert diff_conflict.exists()  # different is not a purge target
    trashed = list((tmp_path / ".trash").rglob(f"*{CONFLICT_SUFFIX}*"))
    assert len(trashed) == 1


def test_replace_apply_swaps_and_backs_up_original(tmp_path):
    orig = tmp_path / "note.md"
    orig.write_text("# old\n", encoding="utf-8")
    conflict = make_conflict(tmp_path, "note.md", "# new\n")

    cc.cmd_replace(
        SimpleNamespace(conflict=str(conflict), root=str(tmp_path), apply=True)
    )

    assert orig.read_text(encoding="utf-8") == "# new\n"
    assert not conflict.exists()
    backed_up = (tmp_path / ".trash").rglob("note.md")
    backup_contents = [p.read_text(encoding="utf-8") for p in backed_up]
    assert backup_contents == ["# old\n"]
