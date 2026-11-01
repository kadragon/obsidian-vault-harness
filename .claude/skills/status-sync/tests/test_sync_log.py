"""CLI replay keeps prior log bytes and is safe to retry after partial closure."""
import json
from pathlib import Path
import subprocess
import sys

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/sync_log.py"


def setup(vault):
    (vault / "_Wiki").mkdir()
    log = vault / "_Wiki/log.md"
    log.write_bytes(b"# Existing log\r\n")
    note = vault / "10_Areas/Example.md"
    note.parent.mkdir()
    note.write_text('---\nstatus: closed\n---\n#업무/학사/수업성적\n', encoding="utf-8")
    report = vault / "close.jsonl"
    rows = [
        {"event": "planned", "paths": ["10_Areas/Example.md", "10_Areas/missing.md"]},
        {"event": "closed", "path": "10_Areas/Example.md", "recorded_at": "2026-11-01T12:00:00"},
        {"event": "failed", "path": "10_Areas/missing.md"},
    ]
    report.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    return log, note, report


def run(vault, report, apply=True):
    return subprocess.run([sys.executable, str(SCRIPT), str(report), "--vault", str(vault)]
                          + (["--apply"] if apply else []), capture_output=True, text=True)


def test_replay_preview_apply_and_retry(tmp_path):
    log, note, report = setup(tmp_path)
    before = log.read_bytes()
    assert run(tmp_path, report, False).returncode == 0
    assert log.read_bytes() == before
    result = run(tmp_path, report)
    assert result.returncode == 0, result.stdout
    assert log.read_bytes().startswith(before)
    assert '#closed [[10_Areas/Example]] — 수업성적 종결' in log.read_text()
    after = log.read_bytes()
    assert run(tmp_path, report).returncode == 0
    assert log.read_bytes() == after
    assert note.read_text().startswith('---\nstatus: closed')


def test_existing_extension_entry_and_unresolved_plan(tmp_path):
    log, note, report = setup(tmp_path)
    log.write_text('- 2026-11-01 #closed [[10_Areas/Example.md]] — unknown 종결\n', encoding="utf-8")
    with report.open("a") as stream:
        stream.write('\n' + json.dumps({"event": "planned", "paths": ["10_Areas/interrupted.md"]}))
    before = log.read_bytes()
    result = run(tmp_path, report)
    assert result.returncode == 1
    assert json.loads(result.stdout)["pending"] == ["10_Areas/interrupted.md"]
    assert log.read_bytes() == before


def test_dot_or_backslash_planned_path_matches_normalized_result(tmp_path):
    log, note, report = setup(tmp_path)
    rows = [
        {"event": "planned", "paths": ["./10_Areas/Example.md", "10_Areas\\missing.md"]},
        {"event": "closed", "path": "10_Areas/Example.md", "recorded_at": "2026-11-01T12:00:00"},
        {"event": "failed", "path": "10_Areas/missing.md"},
    ]
    report.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    result = run(tmp_path, report)
    assert result.returncode == 0, result.stdout
    assert json.loads(result.stdout)["pending"] == []


def test_reopened_note_is_not_logged(tmp_path):
    log, note, report = setup(tmp_path)
    note.write_text('---\nstatus: open\n---\n', encoding="utf-8")
    before = log.read_bytes()
    assert run(tmp_path, report).returncode == 1
    assert log.read_bytes() == before


def test_bad_report_or_existing_lock_never_changes_log(tmp_path):
    log, note, report = setup(tmp_path)
    before = log.read_bytes()
    lock = log.with_name('.status-sync-log.lock')
    lock.write_text('busy')
    assert run(tmp_path, report).returncode == 1
    assert lock.exists() and log.read_bytes() == before
    lock.unlink()
    with report.open('a') as stream:
        stream.write('\n{broken')
    assert run(tmp_path, report).returncode == 1
    assert log.read_bytes() == before


def test_outside_note_path_is_rejected_before_any_append(tmp_path):
    log, note, report = setup(tmp_path)
    before = log.read_bytes()
    with report.open('a') as stream:
        stream.write('\n' + json.dumps({"event": "closed", "path": "../outside.md", "recorded_at": "2026-11-01T12:00:00"}))
    assert run(tmp_path, report).returncode == 1
    assert log.read_bytes() == before
