#!/usr/bin/env python3
"""Regression tests for Inbox's durable source-copy and cleanup gate.

Run directly because tests below ``.claude/`` are intentionally not pytest
collection targets: ``python3 .../test_copy_verified.py`` must exit 0.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unicodedata
import unittest
from pathlib import Path


HERE = Path(__file__).resolve()
SCRIPT = HERE.parent.parent / "scripts" / "copy_verified.py"
spec = importlib.util.spec_from_file_location("copy_verified", SCRIPT)
assert spec and spec.loader
copy_verified = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = copy_verified
spec.loader.exec_module(copy_verified)


class DurableCopyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self.tmp.name) / "vault"
        (self.vault / "_Sources" / "_Assets" / "기타").mkdir(parents=True)
        (self.vault / "10_Areas" / "개발공통" / "202609_업무").mkdir(parents=True)
        self.source = Path(self.tmp.name) / "01_Inbox" / "자료.pdf"
        self.source.parent.mkdir()
        self.source.write_bytes(b"source bytes\x00\xff\n")

    def tearDown(self):
        self.tmp.cleanup()

    def test_copy_reports_actual_asset_link_and_preserves_source(self):
        result = copy_verified.copy_verified(
            self.source,
            "_Sources/_Assets/기타",
            self.vault,
        )

        destination = self.vault / "_Sources" / "_Assets" / "기타" / "자료.pdf"
        self.assertEqual("copied", result.status)
        self.assertTrue(result.verified)
        self.assertEqual("[[_Sources/_Assets/기타/자료.pdf]]", result.wikilink)
        self.assertEqual(self.source.read_bytes(), destination.read_bytes())
        self.assertTrue(self.source.exists())

    def test_different_collision_gets_suffix_without_overwrite(self):
        target_dir = self.vault / "_Sources" / "_Assets" / "기타"
        (target_dir / "자료.pdf").write_bytes(b"older bytes")

        result = copy_verified.copy_verified(self.source, target_dir, self.vault)

        self.assertEqual((target_dir / "자료_2.pdf").resolve(), Path(result.destination))
        self.assertEqual(b"older bytes", (target_dir / "자료.pdf").read_bytes())
        self.assertEqual(self.source.read_bytes(), (target_dir / "자료_2.pdf").read_bytes())

    def test_identical_collision_is_reused(self):
        target_dir = self.vault / "_Sources" / "_Assets" / "기타"
        (target_dir / "자료.pdf").write_bytes(self.source.read_bytes())

        result = copy_verified.copy_verified(self.source, target_dir, self.vault)

        self.assertEqual("reused", result.status)
        self.assertTrue(result.verified)
        self.assertFalse((target_dir / "자료_2.pdf").exists())

    def test_dry_run_does_not_create_copy_or_directory(self):
        result = copy_verified.copy_verified(
            self.source,
            "_Sources/_Assets/new-domain",
            self.vault,
            dry_run=True,
        )

        self.assertEqual("dry-run", result.status)
        self.assertFalse(result.verified)
        self.assertFalse((self.vault / "_Sources" / "_Assets" / "new-domain").exists())
        self.assertTrue(self.source.exists())

    def test_symlink_destination_fails_closed_and_cannot_escape_vault(self):
        outside = Path(self.tmp.name) / "outside"
        outside.mkdir()
        link = self.vault / "_Sources" / "_Assets" / "escape"
        link.symlink_to(outside, target_is_directory=True)

        with self.assertRaises(copy_verified.CopyError):
            copy_verified.copy_verified(self.source, link, self.vault)

        self.assertFalse((outside / self.source.name).exists())
        self.assertTrue(self.source.exists())

    def test_inbox_destination_and_same_file_are_not_durable(self):
        with self.assertRaises(copy_verified.CopyError):
            copy_verified.copy_verified(self.source, self.source.parent, self.vault)

        durable = self.vault / "10_Areas" / "개발공통" / "202609_업무"
        durable_source = durable / "자료.pdf"
        durable_source.write_bytes(self.source.read_bytes())
        with self.assertRaises(copy_verified.CopyError):
            copy_verified.copy_verified(durable_source, durable, self.vault)

    def test_unrepresentable_filename_is_rejected(self):
        with self.assertRaises(copy_verified.CopyError):
            copy_verified.copy_verified(
                self.source,
                "_Sources/_Assets/기타",
                self.vault,
                destination_name="자료#본문.pdf",
            )

    def test_verify_link_requires_exact_link_and_byte_identity(self):
        result = copy_verified.copy_verified(
            self.source,
            "_Sources/_Assets/기타",
            self.vault,
        )
        note = self.vault / "_Sources" / "기타.md"
        note.write_text(f"원본 파일: {result.wikilink}\n", encoding="utf-8")

        checked = copy_verified.verify_link(
            self.source,
            note,
            result.destination,
            self.vault,
        )
        self.assertTrue(checked["verified"])
        self.assertTrue(checked["link_present"])

        Path(result.destination).write_bytes(b"tampered")
        with self.assertRaises(copy_verified.CopyError):
            copy_verified.verify_link(self.source, note, result.destination, self.vault)

    def test_vault_relative_note_path_resolves_like_destination(self):
        """A note path is read against the vault, not the process CWD."""
        result = copy_verified.copy_verified(
            self.source,
            "_Sources/_Assets/기타",
            self.vault,
        )
        note = self.vault / "_Sources" / "기타.md"
        note.write_text(f"원본 파일: {result.wikilink}\n", encoding="utf-8")

        checked = copy_verified.verify_link(
            self.source,
            "_Sources/기타.md",
            result.destination,
            self.vault,
        )
        self.assertTrue(checked["verified"])
        self.assertEqual(str(note.resolve()), checked["note"])

        outside = Path(self.tmp.name) / "밖.md"
        outside.write_text(f"원본 파일: {result.wikilink}\n", encoding="utf-8")
        with self.assertRaises(copy_verified.CopyError):
            copy_verified.verify_link(
                self.source, outside, result.destination, self.vault
            )

    def test_missing_final_link_blocks_cleanup(self):
        result = copy_verified.copy_verified(
            self.source,
            "_Sources/_Assets/기타",
            self.vault,
        )
        note = self.vault / "_Sources" / "기타.md"
        note.write_text("원본 파일: 01_Inbox/자료.pdf\n", encoding="utf-8")

        with self.assertRaises(copy_verified.CopyError):
            copy_verified.verify_link(self.source, note, result.destination, self.vault)
        self.assertTrue(self.source.exists())

    def test_code_and_comment_mentions_do_not_authorize_cleanup(self):
        result = copy_verified.copy_verified(
            self.source,
            "_Sources/_Assets/기타",
            self.vault,
        )
        note = self.vault / "_Sources" / "기타.md"
        note.write_text(
            "```\n" + result.wikilink + "\n```\n"
            "<!-- " + result.wikilink + " -->\n"
            "`" + result.wikilink + "`\n",
            encoding="utf-8",
        )

        with self.assertRaises(copy_verified.CopyError):
            copy_verified.verify_link(self.source, note, result.destination, self.vault)

        note.write_text("- 원본 파일: " + result.wikilink + "\n", encoding="utf-8")
        self.assertTrue(
            copy_verified.verify_link(
                self.source, note, result.destination, self.vault
            )["verified"]
        )

    def test_decomposed_filename_matches_composed_note_link(self):
        """macOS stores 한글 filenames as NFD; notes carry the NFC spelling."""
        decomposed = Path(self.tmp.name) / "01_Inbox" / unicodedata.normalize(
            "NFD", "학사자료.pdf"
        )
        decomposed.write_bytes(b"decomposed source\n")
        result = copy_verified.copy_verified(
            decomposed,
            "_Sources/_Assets/기타",
            self.vault,
        )
        note = self.vault / "_Sources" / "기타.md"
        note.write_text(
            "원본 파일: " + unicodedata.normalize("NFC", result.wikilink) + "\n",
            encoding="utf-8",
        )
        checked = copy_verified.verify_link(
            decomposed, note, result.destination, self.vault
        )
        self.assertTrue(checked["verified"])

    def test_unpaired_backtick_cannot_expose_a_fenced_example_link(self):
        """Fences are stripped before inline code, so a stray ` cannot leak one."""
        result = copy_verified.copy_verified(
            self.source,
            "_Sources/_Assets/기타",
            self.vault,
        )
        note = self.vault / "_Sources" / "기타.md"
        note.write_text(
            "여기 `짝 없는 백틱\n\n```\n예시: " + result.wikilink + "\n```\n",
            encoding="utf-8",
        )
        with self.assertRaises(copy_verified.CopyError):
            copy_verified.verify_link(
                self.source, note, result.destination, self.vault
            )

    def test_nested_fence_cannot_expose_an_example_link(self):
        """A ```` wrapper holding a ``` block stays closed until its own end."""
        result = copy_verified.copy_verified(
            self.source,
            "_Sources/_Assets/기타",
            self.vault,
        )
        note = self.vault / "_Sources" / "기타.md"
        note.write_text(
            "````\n```markdown\n예시: " + result.wikilink + "\n```\n````\n",
            encoding="utf-8",
        )
        with self.assertRaises(copy_verified.CopyError):
            copy_verified.verify_link(
                self.source, note, result.destination, self.vault
            )

    def test_attachment_embed_counts_as_the_final_link(self):
        """Attachment embeds are allowed by Golden Principle #2."""
        result = copy_verified.copy_verified(
            self.source,
            "_Sources/_Assets/기타",
            self.vault,
        )
        note = self.vault / "_Sources" / "기타.md"
        note.write_text("원본 파일: !" + result.wikilink + "\n", encoding="utf-8")
        checked = copy_verified.verify_link(
            self.source, note, result.destination, self.vault
        )
        self.assertTrue(checked["verified"])

    def test_cli_emits_json_and_nonzero_for_bad_source(self):
        good = copy_verified.main(
            ["copy", str(self.source), "_Sources/_Assets/기타", "--vault", str(self.vault)]
        )
        self.assertEqual(0, good)

        missing = copy_verified.main(
            [
                "copy",
                str(self.source) + ".missing",
                "_Sources/_Assets/기타",
                "--vault",
                str(self.vault),
            ]
        )
        self.assertEqual(1, missing)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(DurableCopyTests)
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    print(f"OK — {result.testsRun} durable-copy regression tests") if result.wasSuccessful() else None
    raise SystemExit(0 if result.wasSuccessful() else 1)
