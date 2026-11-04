"""Dispatch recording CLI roundtrips use only temporary notes."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "record_dispatch.py"
spec = importlib.util.spec_from_file_location("record_dispatch", SCRIPT)
dispatch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dispatch)


def fixture(tmp_path, text=None):
    note = tmp_path / "10_Areas" / "sample.md"
    note.parent.mkdir()
    note.write_text(text or (
        "---\nstatus: open\n---\n# Note\n\n## 할 일\n\n"
        "> [!todo]+ 할 일\n> - [ ] 공문 발송\n\n## 현황\n\n"
        "> [!info]+ 현황\n> - 기존 현황\n\n## 처리 결과\n\n유지할 원문\n"
    ), encoding="utf-8", newline="")  # keep LF on Windows; CRLF notes are tested explicitly
    record = {"event_id": "dispatch-20261101-001", "note": "10_Areas/sample.md",
              "dispatched_on": "2026-10-31", "recorded_on": "2026-11-01",
              "summary": "학사관리과에 공문 발송(정보전산원-123) — 결과 안내",
              "task_line": "> - [ ] 공문 발송"}
    return note, record


def run(tmp_path, record, apply=False):
    payload = tmp_path / "record.json"
    payload.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    return subprocess.run([sys.executable, str(SCRIPT), str(payload), "--vault", str(tmp_path)]
                          + (["--apply"] if apply else []), capture_output=True, text=True)


def test_dry_run_apply_and_idempotent_roundtrip(tmp_path):
    note, record = fixture(tmp_path)
    record["follow_up"] = {"text": "회신 수령"}
    before = note.read_bytes()
    preview = run(tmp_path, record)
    assert preview.returncode == 0, preview.stderr
    assert "DRY RUN" in preview.stdout and "+> - [x] 공문 발송 ✅ 2026-10-31" in preview.stdout
    assert note.read_bytes() == before
    applied = run(tmp_path, record, True)
    assert applied.returncode == 0, applied.stderr
    after = note.read_bytes()
    text = after.decode()
    assert "> - [ ] 회신 수령 ➕ 2026-11-01\n" in text
    assert "📅" not in text and "status: open" in text
    assert "> - 2026-10-31 학사관리과에 공문 발송" in text
    assert "## 처리 결과\n\n유지할 원문\n" in text
    assert run(tmp_path, record, True).stdout.startswith("UNCHANGED")
    assert note.read_bytes() == after
    record["summary"] = "Different confirmed payload"
    rejected = run(tmp_path, record, True)
    assert rejected.returncode == 1 and "different payload" in rejected.stderr
    assert note.read_bytes() == after


def test_new_task_heading_override_crlf_and_bom(tmp_path):
    note, record = fixture(tmp_path)
    original = "\ufeff---\r\nstatus: active\r\n---\r\n## 주요 일정\r\n\r\n## 진행 현황\r\n원문"
    note.write_bytes(original.encode())
    record.pop("task_line")
    record.update(task_text="메일 발송", task_heading="## 주요 일정", status_heading="## 진행 현황",
                  follow_up={"text": "회신 확인", "due": "2026-11-07"})
    result = run(tmp_path, record, True)
    assert result.returncode == 0, result.stderr
    data = note.read_bytes()
    assert data.startswith(b"\xef\xbb\xbf") and b"\n" not in data.replace(b"\r\n", b"")
    assert "status: active" in data.decode()
    assert "- [x] 메일 발송 ➕ 2026-11-01 ✅ 2026-10-31" in data.decode()
    assert "- [ ] 회신 확인 ➕ 2026-11-01 📅 2026-11-07" in data.decode()
    assert run(tmp_path, record, True).stdout.startswith("UNCHANGED")


def test_fenced_task_and_heading_examples_are_ignored(tmp_path):
    note, record = fixture(tmp_path, "---\nstatus: open\n---\n## 할 일\n"
        "```md\n## 현황\n- [ ] 공문 발송\n```\n- [ ] 공문 발송\n## 현황\n기존\n")
    record["task_line"] = "- [ ] 공문 발송"
    result = run(tmp_path, record, True)
    assert result.returncode == 0, result.stderr
    assert "```md\n## 현황\n- [ ] 공문 발송\n```" in note.read_text()
    assert note.read_text().count("✅") == 1


@pytest.mark.parametrize("mutation", ["duplicate_task", "missing_task", "missing_heading", "unclosed_fence",
                                      "callout_then_list"])
def test_ambiguous_or_missing_targets_preserve_note(tmp_path, mutation):
    note, record = fixture(tmp_path)
    text = note.read_text()
    if mutation == "duplicate_task":
        text = text.replace("> - [ ] 공문 발송", "> - [ ] 공문 발송\n> - [ ] 공문 발송")
    elif mutation == "missing_task":
        record["task_line"] = "> - [ ] 없는 업무"
    elif mutation == "missing_heading":
        text = text.replace("## 현황", "## 다른 제목")
    elif mutation == "callout_then_list":
        text = text.replace("> - 기존 현황\n", "> - 기존 현황\n- 2026-10-01 이전 기록\n")
    else:
        text += "```\n"
    note.write_text(text)
    before = note.read_bytes()
    result = run(tmp_path, record, True)
    assert result.returncode == 1 and note.read_bytes() == before


@pytest.mark.parametrize("field", ["dispatched_on", "recorded_on", "due"])
def test_invalid_dates_preserve_note(tmp_path, field):
    note, record = fixture(tmp_path)
    if field == "due":
        record["follow_up"] = {"text": "회신", "due": "2026-02-30"}
    else:
        record[field] = "2026-02-30"
    before = note.read_bytes()
    assert run(tmp_path, record, True).returncode == 1
    assert note.read_bytes() == before


@pytest.mark.parametrize("target", ["../outside.md", "90_Archive/archived.md", "missing.md", "link.md"])
def test_disallowed_paths(tmp_path, target):
    note, record = fixture(tmp_path)
    archive = tmp_path / "90_Archive"
    archive.mkdir()
    (archive / "archived.md").write_bytes(note.read_bytes())
    if target == "link.md":
        (tmp_path / target).symlink_to(note)
    record["note"] = target
    before = note.read_bytes()
    assert run(tmp_path, record, True).returncode == 1
    assert note.read_bytes() == before


def test_stale_source_rejected_before_replace(tmp_path):
    note, record = fixture(tmp_path)
    before = note.read_bytes()
    note.write_text("Concurrent edit\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Source changed"):
        dispatch.atomic_write(note, before, b"Unwanted update", tmp_path.resolve(), record["note"])
    assert note.read_text() == "Concurrent edit\n"
    assert not list(note.parent.glob(".dispatch-*"))
