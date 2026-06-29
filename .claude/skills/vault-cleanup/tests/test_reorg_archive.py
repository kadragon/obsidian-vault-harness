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


if __name__ == "__main__":
    unittest.main()
