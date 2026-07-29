#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path


HERE = Path(__file__).resolve()
SCRIPTS = HERE.parents[1] / "scripts"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


reorg_archive = _load("reorg_archive", SCRIPTS / "reorg_archive.py")


class ClosedLogFallbackTest(unittest.TestCase):
    def test_missing_folder_log_matches_exact_flat_note_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            area = vault / "10_Areas" / "학사"
            area.mkdir(parents=True)
            flattened = area / "202401_원업무.md"
            flattened.write_text(
                "---\nstatus: closed\n---\n\n## 할 일\n\n- [x] 완료\n",
                encoding="utf-8",
            )
            log = vault / "_Wiki" / "log.md"
            log.parent.mkdir()
            log.write_text(
                "- 2024-02-01 #closed [[10_Areas/학사/202401_원업무/202401_원업무.md]]\n",
                encoding="utf-8",
            )

            result = reorg_archive.find_closed(
                vault=vault,
                log_path=log,
                ref=date(2024, 3, 15),
                days=1,
                archive_root=vault / "90_Archive" / "areas",
            )

            self.assertEqual(str(flattened), result["candidates"][0]["current"])
            self.assertEqual([], result["unlogged_closed"])

    def test_missing_folder_log_does_not_match_unrelated_flat_month_note(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            area = vault / "10_Areas" / "학사"
            area.mkdir(parents=True)
            unrelated = area / "202401_다른업무.md"
            unrelated.write_text(
                "---\nstatus: closed\n---\n\n## 할 일\n\n- [x] 완료\n",
                encoding="utf-8",
            )
            log = vault / "_Wiki" / "log.md"
            log.parent.mkdir()
            log.write_text(
                "- 2024-02-01 #closed [[10_Areas/학사/202401_원업무/202401_원업무.md]]\n",
                encoding="utf-8",
            )

            result = reorg_archive.find_closed(
                vault=vault,
                log_path=log,
                ref=date(2024, 3, 15),
                days=1,
                archive_root=vault / "90_Archive" / "areas",
            )

            self.assertEqual([], result["candidates"])
            self.assertEqual(["10_Areas/학사/202401_다른업무.md"], result["unlogged_closed"])


class BareWrapperSweepTest(unittest.TestCase):
    """find-bare-wrappers must match check-folder-rules.py Rule 3's verdict."""

    def _areas(self, tmp: str) -> Path:
        areas = Path(tmp) / "10_Areas"
        areas.mkdir(parents=True)
        return areas

    def test_wrapper_with_only_one_note_is_bare(self):
        with tempfile.TemporaryDirectory() as tmp:
            areas = self._areas(tmp)
            wrapper = areas / "학사" / "202401_성적정정"
            wrapper.mkdir(parents=True)
            (wrapper / "_202401_성적정정.md").write_text("본문\n", encoding="utf-8")

            rows = reorg_archive.find_bare_wrappers(areas)

            self.assertEqual(1, len(rows))
            self.assertEqual(str(wrapper), rows[0].current)
            self.assertEqual("학사", rows[0].area)
            # `_` prefix dropped when flattened to the area root (conventions.md)
            self.assertEqual(str(areas / "학사" / "202401_성적정정.md"),
                             rows[0].suggested)

    def test_wrapper_holding_an_attachment_is_not_bare(self):
        with tempfile.TemporaryDirectory() as tmp:
            areas = self._areas(tmp)
            wrapper = areas / "학사" / "202401_성적정정"
            wrapper.mkdir(parents=True)
            (wrapper / "_202401_성적정정.md").write_text("본문\n", encoding="utf-8")
            (wrapper / "공문.pdf").write_bytes(b"%PDF-1.4\n")

            self.assertEqual([], reorg_archive.find_bare_wrappers(areas))

    def test_attachment_in_a_subfolder_still_counts(self):
        """Regression: counting direct children only called a wrapper holding
        147 nested attachments 무첨부 (실볼트 오탐 5건, 2026-07-29)."""
        with tempfile.TemporaryDirectory() as tmp:
            areas = self._areas(tmp)
            wrapper = areas / "과업심의" / "202605_제4차과업심의"
            (wrapper / "2026-012" / "결과물").mkdir(parents=True)
            (wrapper / "_202605_제4차과업심의.md").write_text("본문\n", encoding="utf-8")
            (wrapper / "2026-012" / "결과물" / "심의결과.pdf").write_bytes(b"%PDF-1.4\n")

            self.assertEqual([], reorg_archive.find_bare_wrappers(areas))

    def test_note_in_a_subfolder_counts_toward_md_total(self):
        with tempfile.TemporaryDirectory() as tmp:
            areas = self._areas(tmp)
            wrapper = areas / "학사" / "202401_성적정정"
            (wrapper / "하위").mkdir(parents=True)
            (wrapper / "_202401_성적정정.md").write_text("본문\n", encoding="utf-8")
            (wrapper / "하위" / "메모.md").write_text("본문\n", encoding="utf-8")

            self.assertEqual([], reorg_archive.find_bare_wrappers(areas))

    def test_wrapper_holding_two_notes_is_not_bare(self):
        with tempfile.TemporaryDirectory() as tmp:
            areas = self._areas(tmp)
            wrapper = areas / "학사" / "202401_성적정정"
            wrapper.mkdir(parents=True)
            (wrapper / "_202401_성적정정.md").write_text("본문\n", encoding="utf-8")
            (wrapper / "회신.md").write_text("본문\n", encoding="utf-8")

            self.assertEqual([], reorg_archive.find_bare_wrappers(areas))

    def test_flat_note_at_area_root_is_not_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            areas = self._areas(tmp)
            area = areas / "학사"
            area.mkdir(parents=True)
            (area / "202401_성적정정.md").write_text("본문\n", encoding="utf-8")

            self.assertEqual([], reorg_archive.find_bare_wrappers(areas))

    def test_empty_wrapper_suggests_folder_name_as_flat_note(self):
        with tempfile.TemporaryDirectory() as tmp:
            areas = self._areas(tmp)
            wrapper = areas / "학사" / "202401_성적정정"
            wrapper.mkdir(parents=True)

            rows = reorg_archive.find_bare_wrappers(areas)

            self.assertEqual(1, len(rows))
            self.assertEqual("", rows[0].note)
            self.assertEqual(str(areas / "학사" / "202401_성적정정.md"),
                             rows[0].suggested)

    def test_missing_areas_root_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual([],
                             reorg_archive.find_bare_wrappers(Path(tmp) / "없음"))


if __name__ == "__main__":
    unittest.main()
