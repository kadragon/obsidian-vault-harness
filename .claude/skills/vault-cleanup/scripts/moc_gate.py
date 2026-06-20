#!/usr/bin/env python3
"""MOC workflow-gate detector (AGENTS.md → Workflow Gates).

Flags 10_Areas domains that crossed the MOC threshold but have no operational
MOC yet. Detection only — MOC authoring stays with vault-navigator (사전조사)
+ obsidian-operator (생성). Run periodically / during vault-cleanup.

Thresholds (AGENTS.md): 도메인 노트 20+ 누적, 또는 동일 인시던트 유형 3회+.
The note-count gate is exact; recurring-incident-type is judgment, so this
script approximates it with raw incident volume (`--incident-threshold`) and
leaves the "3+ distinct recurring types" call to the human/agent.

Usage:
    python moc_gate.py <vault> [--note-threshold 20] [--incident-threshold 10] [--json]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def existing_mocs(topics_dir: Path) -> set[str]:
    """Domain names that already have `{domain}-운영-MOC.md`."""
    out: set[str] = set()
    if not topics_dir.exists():
        return out
    suffix = "-운영-MOC.md"  # NFC literal; filenames may be NFD (macOS)
    for p in topics_dir.glob("*-MOC.md"):  # ASCII glob — Korean glob misses NFD
        nm = _nfc(p.name)
        if nm.endswith(suffix):
            out.add(nm[: -len(suffix)])
    return out


def domain_stats(vault: Path) -> dict[str, dict]:
    areas = vault / "10_Areas"
    incident_dir = vault / "14_Changes" / "incident"
    stats: dict[str, dict] = {}
    if not areas.exists():
        return stats
    for d in sorted(p for p in areas.iterdir() if p.is_dir()):
        name = _nfc(d.name)
        note_count = sum(1 for _ in d.rglob("*.md"))
        stats[name] = {"notes": note_count, "incidents": 0}
    # incident volume per domain: count incident notes carrying #업무/{domain}
    if incident_dir.exists():
        for md in incident_dir.rglob("*.md"):
            try:
                text = md.read_text(encoding="utf-8")
            except OSError:
                continue
            for name in stats:
                if re.search(r'#업무/' + re.escape(name) + r'(?:[/\s]|$)', text):
                    stats[name]["incidents"] += 1
    return stats


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("vault", type=Path)
    ap.add_argument("--note-threshold", type=int, default=20)
    ap.add_argument("--incident-threshold", type=int, default=10)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    vault = args.vault.resolve()
    mocs = existing_mocs(vault / "_Wiki" / "topics")
    stats = domain_stats(vault)

    gaps, ok, below = [], [], []
    for name, s in stats.items():
        over = s["notes"] >= args.note_threshold or s["incidents"] >= args.incident_threshold
        rec = {"domain": name, "has_moc": name in mocs, **s}
        if over and name not in mocs:
            gaps.append(rec)
        elif over:
            ok.append(rec)
        else:
            below.append(rec)
    gaps.sort(key=lambda r: -r["notes"])

    if args.json:
        print(json.dumps({"gaps": gaps, "ok": ok, "below": below},
                         ensure_ascii=False, indent=2))
    else:
        print(f"## MOC 게이트 — 신규 필요 ({len(gaps)})  "
              f"[임계: 노트≥{args.note_threshold} 또는 인시던트≥{args.incident_threshold}]")
        for r in gaps:
            print(f"  ⚠ {r['domain']}: 노트 {r['notes']}, 인시던트 {r['incidents']} — MOC 없음 → 생성 권장")
        print(f"\n## MOC 보유·임계 충족 ({len(ok)})")
        for r in ok:
            print(f"  ✓ {r['domain']}: 노트 {r['notes']}, 인시던트 {r['incidents']}")
        print(f"\n## 임계 미달 ({len(below)})")
        for r in below:
            print(f"  · {r['domain']}: 노트 {r['notes']}, 인시던트 {r['incidents']}"
                  + ("  (MOC 있음)" if r["has_moc"] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
