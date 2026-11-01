#!/usr/bin/env python3
"""Exercise Inbox cleanup with real temporary files, never live vault content."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import cleanup_completed as cleaner


class CleanupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.vault = Path(self.tmp.name) / "vault"
        for folder in ("01_Inbox/action/job", "01_Inbox/reference", "10_Areas/Test", "_Sources/_Assets/Test"):
            (self.vault / folder).mkdir(parents=True)

    def write(self, name, data):
        path = self.vault / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data.encode("utf-8") if isinstance(data, str) else data)
        return path

    def digest(self, name):
        return hashlib.sha256((self.vault / name).read_bytes()).hexdigest()

    def item(self, source="01_Inbox/action/job/a.pdf", branch="action", text=False):
        note = "10_Areas/Test/note.md" if branch == "action" else "_Sources/note.md"
        durable = "text-absorbed" if text else "_Sources/_Assets/Test/a.pdf"
        self.write(source, "full source\n")
        self.write(note, "---\ntype: work\n---\nfull source\n" if text else f"[[{durable}]]\n")
        if not text:
            self.write(durable, "full source\n")
        return dict(source=source, note=note, durable=durable, branch=branch,
                    completed=True, quality="PASS", hold=False,
                    source_sha256=self.digest(source), note_sha256=self.digest(note))

    def manifest(self, *items, scope=None):
        return {"version": 1, "scope": scope or ["01_Inbox/action/job"], "files": list(items)}

    def run_cleanup(self, item, apply=True, scope=None):
        return cleaner.cleanup(self.manifest(item, scope=scope), self.vault, apply)

    def test_dry_run_preserves_then_apply_deletes_only_source(self):
        item = self.item()
        before = self.run_cleanup(item, False)
        self.assertEqual(before["ready"], 1)
        self.assertTrue((self.vault / item["source"]).exists())
        after = self.run_cleanup(item)
        self.assertEqual(after["deleted"], 1)
        self.assertTrue(after["ok"])
        self.assertFalse((self.vault / item["source"]).exists())
        self.assertTrue((self.vault / item["note"]).exists())
        self.assertTrue((self.vault / item["durable"]).exists())
        self.assertFalse((self.vault / "01_Inbox/action/job").exists())
        self.assertTrue((self.vault / "01_Inbox/action").exists())
        self.assertFalse((self.vault / ".trash").exists())

    def test_unlisted_and_held_files_remain_with_partial_success(self):
        first = self.item()
        held = dict(first, source="01_Inbox/action/job/held.pdf", hold=True)
        self.write(held["source"], "full source\n")
        unknown = self.write("01_Inbox/action/job/unknown.hwp", "unknown")
        result = cleaner.cleanup(self.manifest(first, held), self.vault, True)
        self.assertEqual(result["deleted"], 1)
        self.assertEqual(result["preserved"], 2)
        self.assertTrue(unknown.exists())
        self.assertTrue((self.vault / held["source"]).exists())
        self.assertTrue(unknown.parent.exists())

    def test_missing_quality_completion_or_hold_blocks(self):
        for key, value in (("completed", False), ("quality", "UNVERIFIED"), ("hold", True), ("hold", None)):
            item = self.item()
            item[key] = value
            result = self.run_cleanup(item)
            self.assertFalse(result["ok"])
            self.assertTrue((self.vault / item["source"]).exists())

    def test_source_note_and_copy_changes_block(self):
        for key in ("source", "note", "durable"):
            item = self.item()
            self.write(item[key], "changed")
            self.assertFalse(self.run_cleanup(item)["ok"])
            self.assertTrue((self.vault / item["source"]).exists())

    def test_reference_needs_real_exact_link(self):
        item = self.item(branch="reference", source="01_Inbox/reference/a.pdf")
        self.write(item["note"], "```\n[[" + item["durable"] + "]]\n```\n")
        item["note_sha256"] = self.digest(item["note"])
        result = self.run_cleanup(item, scope=["01_Inbox/reference"])
        self.assertFalse(result["ok"])
        self.write(item["note"], "[[" + item["durable"] + "]]\n")
        item["note_sha256"] = self.digest(item["note"])
        self.assertTrue(self.run_cleanup(item, scope=["01_Inbox/reference"])["ok"])

    def test_reference_markdown_keeps_byte_identical_md_txt_attachment(self):
        source = self.write("01_Inbox/reference/article.md", "# 원문\n\n본문과 출처\n")
        copied = cleaner.copies.copy_verified(
            source, "_Sources/_Assets/Test", self.vault, destination_name="article.md.txt")
        note = self.write("_Sources/article.md", "# 정리\n" + copied.wikilink + "\n")
        item = dict(source=str(source), note=str(note), durable=copied.destination,
                    branch="reference", completed=True, quality="PASS", hold=False,
                    source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                    note_sha256=hashlib.sha256(note.read_bytes()).hexdigest())
        expected = source.read_bytes()
        result = self.run_cleanup(item, scope=["01_Inbox/reference"])
        self.assertTrue(result["ok"])
        self.assertFalse(source.exists())
        self.assertEqual(Path(copied.destination).read_bytes(), expected)
        self.assertEqual(Path(copied.destination).name, "article.md.txt")

    def test_new_file_during_cleanup_is_preserved_and_reported(self):
        item = self.item()
        real_verify = cleaner.verify
        def add_file(entry, vault):
            self.write("01_Inbox/action/job/new/file.pdf", "new data")
            return real_verify(entry, vault)
        with patch.object(cleaner, "verify", side_effect=add_file):
            result = self.run_cleanup(item)
        self.assertEqual(result["deleted"], 1)
        self.assertEqual(result["preserved"], 1)
        self.assertTrue((self.vault / "01_Inbox/action/job/new/file.pdf").exists())
        self.assertIn("appeared during cleanup", result["results"][-1]["reason"])

    def test_text_absorbed_requires_entire_exact_nonempty_body(self):
        item = self.item("01_Inbox/action/job/a.txt", text=True)
        self.write(item["note"], "---\ntype: work\n---\nsummary only\n")
        item["note_sha256"] = self.digest(item["note"])
        self.assertFalse(self.run_cleanup(item)["ok"])
        self.write(item["note"], "---\ntype: work\n---\nfull source\n")
        item["note_sha256"] = self.digest(item["note"])
        self.assertTrue(self.run_cleanup(item)["ok"])

    def test_text_absorbed_ignores_source_bom_and_crlf(self):
        item = self.item("01_Inbox/action/job/a.txt", text=True)
        self.write(item["source"], b"\xef\xbb\xbffull source\r\nsecond line\r\n")
        item["source_sha256"] = self.digest(item["source"])
        self.write(item["note"], "---\ntype: work\n---\nfull source\nsecond line\n")
        item["note_sha256"] = self.digest(item["note"])
        self.assertTrue(self.run_cleanup(item)["ok"])

    def test_nfd_filename_on_disk_matches_nfc_manifest(self):
        import unicodedata
        nfd = unicodedata.normalize("NFD", "공문.pdf")
        nfc = unicodedata.normalize("NFC", "공문.pdf")
        probe = self.vault / "01_Inbox" / nfd
        probe.write_text("x")
        insensitive = (self.vault / "01_Inbox" / nfc).exists()
        probe.unlink()
        if not insensitive:
            self.skipTest("filesystem is normalization-sensitive")
        item = self.item(f"01_Inbox/action/job/{nfc}")
        (self.vault / item["source"]).unlink()
        self.write(f"01_Inbox/action/job/{nfd}", "full source\n")
        result = self.run_cleanup(item)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["deleted"], 1)

    def test_text_only_in_frontmatter_or_empty_source_is_not_absorbed(self):
        item = self.item("01_Inbox/action/job/a.md", text=True)
        self.write(item["note"], "---\nfull source\n---\nsummary\n")
        item["note_sha256"] = self.digest(item["note"])
        self.assertFalse(self.run_cleanup(item)["ok"])
        self.write(item["source"], "\n")
        item["source_sha256"] = self.digest(item["source"])
        self.assertFalse(self.run_cleanup(item)["ok"])

    def test_absorbed_binary_or_reference_is_rejected(self):
        item = self.item(text=True)
        self.assertFalse(self.run_cleanup(item)["ok"])
        item = self.item("01_Inbox/reference/a.md", branch="reference", text=True)
        self.assertFalse(self.run_cleanup(item, scope=["01_Inbox/reference"])["ok"])

    def test_note_and_durable_must_be_outside_inbox(self):
        for key in ("note", "durable"):
            item = self.item()
            item[key] = item["source"]
            result = self.run_cleanup(item)
            self.assertFalse(result["ok"])
            self.assertTrue((self.vault / item["source"]).exists())

    def test_hardlink_cannot_be_a_durable_copy(self):
        item = self.item()
        durable = self.vault / item["durable"]
        durable.unlink()
        durable.hardlink_to(self.vault / item["source"])
        result = self.run_cleanup(item)
        self.assertFalse(result["ok"])
        self.assertTrue((self.vault / item["source"]).exists())

    def test_symlink_source_note_or_durable_is_rejected(self):
        for key in ("source", "note", "durable"):
            item = self.item()
            original = self.vault / item[key]
            target = original.with_name(original.name + ".real")
            original.rename(target)
            try:
                original.symlink_to(target)
            except OSError as exc:
                self.skipTest(str(exc))
            self.assertFalse(self.run_cleanup(item)["ok"])
            self.assertTrue(original.is_symlink())
            original.unlink()
            target.rename(original)

    def test_scope_outside_inbox_and_parent_traversal_are_rejected(self):
        item = self.item()
        for scope in (["10_Areas"], ["01_Inbox/../10_Areas"]):
            with self.assertRaises(cleaner.CleanupError):
                cleaner.cleanup(self.manifest(item, scope=scope), self.vault, True)
        self.assertTrue((self.vault / item["source"]).exists())

    def test_symlink_directory_in_scope_is_not_followed(self):
        item = self.item()
        outside = Path(self.tmp.name) / "outside"
        outside.mkdir()
        other = outside / "must-stay.pdf"
        other.write_text("outside", encoding="utf-8")
        link = self.vault / "01_Inbox/action/job/linked"
        try:
            link.symlink_to(outside, target_is_directory=True)
        except OSError as exc:
            self.skipTest(str(exc))
        result = self.run_cleanup(item)
        self.assertEqual(result["deleted"], 1)
        self.assertFalse(result["ok"])
        self.assertTrue(other.exists())
        self.assertTrue(link.is_symlink())

    def test_outside_durable_and_symlinked_scope_fail_closed(self):
        item = self.item()
        outside = Path(self.tmp.name) / "outside.pdf"
        outside.write_text("full source\n", encoding="utf-8")
        item["durable"] = str(outside)
        self.assertFalse(self.run_cleanup(item)["ok"])
        alias = self.vault / "01_Inbox/alias"
        try:
            alias.symlink_to(self.vault / "01_Inbox/action/job", target_is_directory=True)
        except OSError as exc:
            self.skipTest(str(exc))
        with self.assertRaises(cleaner.copies.CopyError):
            self.run_cleanup(item, scope=["01_Inbox/alias"])
        self.assertTrue((self.vault / item["source"]).exists())

    def test_file_scope_does_not_touch_siblings_or_unlisted_manifest_target(self):
        item = self.item()
        sibling = self.write("01_Inbox/action/job/sibling.pdf", "full source\n")
        other = dict(item, source="01_Inbox/action/job/sibling.pdf")
        result = cleaner.cleanup(self.manifest(item, other, scope=[item["source"]]), self.vault, True)
        self.assertEqual(result["deleted"], 1)
        self.assertFalse(result["ok"])
        self.assertTrue(sibling.exists())

    def test_duplicate_source_blocks_deletion(self):
        item = self.item()
        result = cleaner.cleanup(self.manifest(item, item), self.vault, True)
        self.assertFalse(result["ok"])
        self.assertTrue((self.vault / item["source"]).exists())

    def test_rechecks_after_preview_before_unlink(self):
        item = self.item()
        real_verify = cleaner.verify
        calls = []
        def mutate_after_first(entry, vault):
            result = real_verify(entry, vault)
            calls.append(result)
            if len(calls) == 1:
                self.write(item["note"], "link removed")
            return result
        with patch.object(cleaner, "verify", side_effect=mutate_after_first):
            result = self.run_cleanup(item)
        self.assertFalse(result["ok"])
        self.assertTrue((self.vault / item["source"]).exists())

    def test_cli_partial_success_nonzero(self):
        item = self.item()
        self.write("01_Inbox/action/job/unknown.txt", "unprocessed")
        path = Path(self.tmp.name) / "manifest.json"
        path.write_text(json.dumps(self.manifest(item)), encoding="utf-8")
        result = subprocess.run([sys.executable, str(SCRIPTS / "cleanup_completed.py"),
                                 str(path), "--vault", str(self.vault), "--apply"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(json.loads(result.stdout)["deleted"], 1)
        self.assertTrue((self.vault / "01_Inbox/action/job/unknown.txt").exists())


if __name__ == "__main__":
    unittest.main()
