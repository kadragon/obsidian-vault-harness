#!/usr/bin/env python3
"""Tests for project-restructure/scripts/restructure.py.

Run with: python3 .claude/skills/project-restructure/tests/test_restructure.py
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve()
SCRIPT = HERE.parents[1] / "scripts" / "restructure.py"


def _load():
    spec = importlib.util.spec_from_file_location("restructure", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["restructure"] = mod
    spec.loader.exec_module(mod)
    return mod


rs = _load()

HUB = """---
type: project
status: active
---

# P

- [x] 심의 완료 ✅ 2026-09-28
- [ ] 계약 📅 2026-10-14
- 심의자료: `과업심의/a.hwpx`
- [[[37. 성과] 보고서.hwpx]]
- [[참고문서/r.pdf]]
"""


def make_vault(root: Path) -> Path:
    proj = root / "12_Projects" / "2026" / "P"
    (proj / "과업심의").mkdir(parents=True)
    (proj / "참고문서").mkdir()
    (proj / "_P.md").write_text(HUB, encoding="utf-8")
    (proj / "과업심의" / "a.hwpx").write_bytes(b"AAA")
    (proj / "참고문서" / "r.pdf").write_bytes(b"RRR")
    (proj / "copy of a.hwpx").write_bytes(b"AAA")
    (proj / "note.md").write_text("# n\n", encoding="utf-8")
    other = root / "90_Archive" / "x"
    other.mkdir(parents=True)
    (other / "[37. 성과] 보고서.hwpx").write_bytes(b"S")
    wiki = root / "_Wiki"
    wiki.mkdir()
    (wiki / "log.md").write_text("- [[12_Projects/2026/P/note]]\n", encoding="utf-8")
    return proj


def write_manifest(path: Path, rows: list[tuple[str, str]]) -> Path:
    path.write_text("from\tto\n" + "".join(f"{a}\t{b}\n" for a, b in rows), encoding="utf-8")
    return path


class ScanTests(unittest.TestCase):
    def test_scan_reports_hub_checkboxes_and_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = make_vault(Path(tmp))
            out = rs.scan(proj)
            self.assertEqual(out["hub"]["checkboxes_open"], 1)
            self.assertEqual(out["hub"]["checkboxes_done"], 1)
            dup_sets = [sorted(g) for g in out["duplicates"]]
            self.assertIn(["copy of a.hwpx", "과업심의/a.hwpx"], dup_sets)
            self.assertIn("note.md", out["root_files"])


class MoveTests(unittest.TestCase):
    def test_preflight_rejects_existing_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = make_vault(Path(tmp))
            m = write_manifest(Path(tmp) / "m.tsv", [("note.md", "_P.md")])
            out = rs.move(proj, m, apply=False)
            self.assertTrue(out["errors"])
            self.assertTrue((proj / "note.md").exists())

    def test_dry_run_does_not_move(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = make_vault(Path(tmp))
            m = write_manifest(Path(tmp) / "m.tsv", [("과업심의", "3. 과업심의")])
            out = rs.move(proj, m, apply=False)
            self.assertFalse(out["errors"])
            self.assertTrue((proj / "과업심의").exists())

    def test_apply_moves_writes_undo_and_prunes_empty_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = make_vault(Path(tmp))
            m = write_manifest(Path(tmp) / "m.tsv", [
                ("참고문서/r.pdf", "99. 참고/r.pdf"),
                ("note.md", "5. 계약/note.md"),
            ])
            out = rs.move(proj, m, apply=True)
            self.assertFalse(out["errors"])
            self.assertTrue((proj / "99. 참고" / "r.pdf").exists())
            self.assertFalse((proj / "참고문서").exists())
            undo = Path(out["undo_manifest"]).read_text(encoding="utf-8")
            self.assertIn("5. 계약/note.md\tnote.md", undo)


class RefsTests(unittest.TestCase):
    def test_refs_finds_relative_and_full_path_references(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = make_vault(Path(tmp))
            m = write_manifest(Path(tmp) / "m.tsv", [
                ("과업심의", "3. 과업심의"),
                ("참고문서/r.pdf", "99. 참고/r.pdf"),
                ("note.md", "5. 계약/note.md"),
            ])
            hits = rs.refs(proj, m)
            found = {(h["file"], h["old"]) for h in hits}
            self.assertIn(("12_Projects/2026/P/_P.md", "과업심의/"), found)
            self.assertIn(("12_Projects/2026/P/_P.md", "참고문서/r.pdf"), found)
            self.assertIn(("_Wiki/log.md", "12_Projects/2026/P/note"), found)

    def test_refs_after_apply_skips_updated_paths_and_detects_dotted_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = make_vault(Path(tmp))
            (proj / "99. 작년 예시").mkdir()
            (proj / "99. 작년 예시" / "e.pdf").write_bytes(b"E")
            m = write_manifest(Path(tmp) / "m.tsv", [
                ("과업심의", "3. 과업심의"),
                ("99. 작년 예시", "99. 참고/작년 예시"),
            ])
            rs.move(proj, m, apply=True)
            (proj / "_P.md").write_text(
                "- `3. 과업심의/a.hwpx`\n- `99. 작년 예시/e.pdf`\n", encoding="utf-8")
            olds = [h["old"] for h in rs.refs(proj, m)]
            self.assertEqual(olds, ["99. 작년 예시/"])

    def test_refs_skips_path_valid_relative_to_note_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = make_vault(Path(tmp))
            m = write_manifest(Path(tmp) / "m.tsv", [("과업심의", "3. 과업심의/과업심의")])
            rs.move(proj, m, apply=True)
            (proj / "_P.md").write_text("no refs\n", encoding="utf-8")
            (proj / "3. 과업심의" / "_stage.md").write_text("- `과업심의/a.hwpx`\n", encoding="utf-8")
            self.assertEqual(rs.refs(proj, m), [])


class VerifyTests(unittest.TestCase):
    def test_nested_bracket_name_resolves_and_path_link_breaks_after_move(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = make_vault(Path(tmp))
            before = rs.verify(proj)
            self.assertEqual(before["missing_links"], [])
            rs.move(proj, write_manifest(Path(tmp) / "m.tsv", [("참고문서/r.pdf", "99. 참고/r.pdf")]), apply=True)
            after = rs.verify(proj, baseline=before)
            self.assertEqual([m["target"] for m in after["missing_links"]], ["참고문서/r.pdf"])
            self.assertFalse(after["ok"])

    def test_baseline_ignores_preexisting_missing_link(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = make_vault(Path(tmp))
            (proj / "_P.md").write_text(HUB + "- [[없는 파일.hwpx]]\n", encoding="utf-8")
            before = rs.verify(proj)
            after = rs.verify(proj, baseline=before)
            self.assertTrue(after["ok"])
            self.assertEqual(len(after["missing_links"]), 1)

    def test_hub_checkbox_loss_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = make_vault(Path(tmp))
            before = rs.verify(proj)
            (proj / "_P.md").write_text(HUB.replace("- [ ] 계약 📅 2026-10-14\n", ""), encoding="utf-8")
            after = rs.verify(proj, baseline=before)
            self.assertFalse(after["ok"])
            self.assertIn("hub_checkboxes", " ".join(after["failures"]))

    def test_attachment_loss_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = make_vault(Path(tmp))
            before = rs.verify(proj)
            (proj / "copy of a.hwpx").unlink()
            after = rs.verify(proj, baseline=before)
            self.assertFalse(after["ok"])

    def test_cli_out_file_feeds_baseline(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = make_vault(Path(tmp))
            before = Path(tmp) / "before.json"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(rs.main(["verify", str(proj), "--out", str(before)]), 0)
                self.assertEqual(rs.main(["verify", str(proj), "--baseline", str(before)]), 0)
            self.assertTrue(json.loads(before.read_text(encoding="utf-8"))["ok"])


if __name__ == "__main__":
    unittest.main()
