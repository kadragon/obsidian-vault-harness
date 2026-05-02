"""
conflict_cleanup.py — Syncthing conflict file helper for Obsidian vault.

Subcommands:
  scan [--root DIR] [--json]           Find all *.sync-conflict-* files
  purge [--root DIR] [--apply]         Delete SHA-256-identical conflicts
  delete <conflict> [--apply]          Delete a single conflict file
  replace <conflict> [--apply]         Replace original with conflict file
"""

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

CONFLICT_RE = re.compile(
    r"\.sync-conflict-\d{8}-\d{6}-[A-Z0-9]+(?=\.[^.]+$)"
)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def original_path(conflict: Path) -> Path:
    name = conflict.name
    new_name = CONFLICT_RE.sub("", name)
    return conflict.parent / new_name


def classify(conflict: Path) -> dict:
    orig = original_path(conflict)
    is_md = conflict.suffix.lower() == ".md"
    stat_c = conflict.stat()

    base = {
        "conflict": str(conflict),
        "original": str(orig),
        "conflict_size": stat_c.st_size,
        "conflict_mtime": datetime.fromtimestamp(stat_c.st_mtime).strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        "original_size": None,
        "original_mtime": None,
    }

    if not orig.exists():
        return {**base, "status": "orphan"}

    if not is_md:
        stat_o = orig.stat()
        return {
            **base,
            "status": "non-text",
            "original_size": stat_o.st_size,
            "original_mtime": datetime.fromtimestamp(stat_o.st_mtime).strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
        }

    stat_o = orig.stat()
    identical = sha256(conflict) == sha256(orig)
    return {
        **base,
        "status": "identical" if identical else "different",
        "original_size": stat_o.st_size,
        "original_mtime": datetime.fromtimestamp(stat_o.st_mtime).strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
    }


def find_conflicts(root: Path) -> list[Path]:
    results = []
    for path in root.rglob("*"):
        if path.is_file() and CONFLICT_RE.search(path.name):
            results.append(path)
    return sorted(results)


def cmd_scan(args):
    root = Path(args.root).resolve()
    conflicts = find_conflicts(root)

    items = [classify(c) for c in conflicts]

    if args.json:
        print(json.dumps(items, ensure_ascii=False, indent=2))
        return

    if not items:
        print("Conflict 파일 없음.")
        return

    counts = {"identical": 0, "different": 0, "orphan": 0, "non-text": 0}
    for item in items:
        counts[item["status"]] += 1

    print(f"총 {len(items)}개 conflict 파일 발견:\n")
    for status, count in counts.items():
        if count:
            print(f"  {status}: {count}개")

    print()
    status_label = {
        "identical": "[동일]",
        "different": "[차이]",
        "orphan":    "[원본없음]",
        "non-text":  "[비텍스트]",
    }
    for item in items:
        label = status_label[item["status"]]
        print(f"{label} {item['conflict']}")


def cmd_purge(args):
    root = Path(args.root).resolve()
    conflicts = find_conflicts(root)
    targets = [c for c in conflicts if classify(c)["status"] == "identical"]

    if not targets:
        print("삭제할 identical conflict 없음.")
        return

    if not args.apply:
        print("[DRY-RUN] 삭제 예정:")
        for c in targets:
            print(f"  {c}  (원본과 동일)")
        print(f"\n총 {len(targets)}개 파일이 삭제될 예정입니다. (원본 파일은 변경되지 않습니다.)")
        print("실제 삭제하려면 --apply 옵션을 추가하세요.")
        return

    deleted = 0
    for c in targets:
        c.unlink()
        print(f"삭제됨: {c}")
        deleted += 1
    print(f"\n{deleted}개 conflict 파일 삭제 완료.")


def cmd_delete(args):
    conflict = Path(args.conflict).resolve()
    if not conflict.exists():
        print(f"오류: 파일이 없습니다 — {conflict}", file=sys.stderr)
        sys.exit(1)

    if not CONFLICT_RE.search(conflict.name):
        print(
            f"오류: 파일명에 .sync-conflict- 패턴이 없습니다 — {conflict.name}\n"
            "안전 규칙: conflict 파일만 삭제할 수 있습니다.",
            file=sys.stderr,
        )
        sys.exit(1)

    if not args.apply:
        print(f"[DRY-RUN] 삭제 예정: {conflict}")
        print("실제 삭제하려면 --apply를 추가하세요.")
        return

    conflict.unlink()
    print(f"삭제됨: {conflict}")


def cmd_replace(args):
    conflict = Path(args.conflict).resolve()
    if not conflict.exists():
        print(f"오류: 파일이 없습니다 — {conflict}", file=sys.stderr)
        sys.exit(1)

    if not CONFLICT_RE.search(conflict.name):
        print(
            f"오류: 파일명에 .sync-conflict- 패턴이 없습니다 — {conflict.name}",
            file=sys.stderr,
        )
        sys.exit(1)

    orig = original_path(conflict)

    if not args.apply:
        if orig.exists():
            print(f"[DRY-RUN] 원본 삭제 예정:  {orig}")
        else:
            print(f"[DRY-RUN] 원본 없음 (orphan 복원):  {orig}")
        print(f"[DRY-RUN] Conflict rename 예정: {conflict} → {orig}")
        print("실제 실행하려면 --apply를 추가하세요.")
        return

    if orig.exists():
        orig.unlink()
        print(f"원본 삭제됨: {orig}")

    conflict.rename(orig)
    print(f"Conflict → 원본으로 이동: {orig}")


def main():
    parser = argparse.ArgumentParser(description="Syncthing conflict cleanup helper")
    sub = parser.add_subparsers(dest="cmd")

    p_scan = sub.add_parser("scan", help="Conflict 파일 탐색 및 분류")
    p_scan.add_argument("--root", default=".", help="볼트 루트 경로 (기본: 현재 디렉토리)")
    p_scan.add_argument("--json", action="store_true", help="JSON 형식으로 출력")

    p_purge = sub.add_parser("purge", help="SHA-256 동일 conflict 삭제")
    p_purge.add_argument("--root", default=".", help="볼트 루트 경로")
    p_purge.add_argument("--apply", action="store_true", help="실제 삭제 실행 (기본: dry-run)")

    p_delete = sub.add_parser("delete", help="특정 conflict 파일 삭제")
    p_delete.add_argument("conflict", help="삭제할 conflict 파일 경로")
    p_delete.add_argument("--apply", action="store_true", help="실제 삭제 실행")

    p_replace = sub.add_parser("replace", help="Conflict로 원본 교체")
    p_replace.add_argument("conflict", help="원본으로 올릴 conflict 파일 경로")
    p_replace.add_argument("--apply", action="store_true", help="실제 실행")

    args = parser.parse_args()

    if args.cmd == "scan":
        cmd_scan(args)
    elif args.cmd == "purge":
        cmd_purge(args)
    elif args.cmd == "delete":
        cmd_delete(args)
    elif args.cmd == "replace":
        cmd_replace(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
