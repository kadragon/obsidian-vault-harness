"""Fail when an hwpx has text paragraphs that are left-aligned.

Official documents use justified body text; LEFT usually leaks in from a
style-reference file's paraPr. Usage:

    python3 check_align.py <file.hwpx | unpacked dir>

Exit 0 = no left-aligned text paragraph, 1 = found (listed), 2 = unreadable.
Fix: set <hh:align horizontal="JUSTIFY"> on the listed paraPr ids in header.xml
before packing.
"""
import re
import sys
import zipfile
from pathlib import Path


def load(target):
    p = Path(target)
    if p.is_dir():
        header = (p / "Contents" / "header.xml").read_text(encoding="utf-8")
        sections = [f.read_text(encoding="utf-8") for f in sorted((p / "Contents").glob("section*.xml"))]
    else:
        with zipfile.ZipFile(p) as z:
            header = z.read("Contents/header.xml").decode("utf-8")
            names = sorted(n for n in z.namelist() if re.fullmatch(r"Contents/section\d+\.xml", n))
            sections = [z.read(n).decode("utf-8") for n in names]
    return header, sections


def left_ids(header):
    ids = set()
    for m in re.finditer(r'<hh:paraPr id="(\d+)".*?</hh:paraPr>', header, flags=re.S):
        align = re.search(r'<hh:align horizontal="(\w+)"', m.group(0))
        if align and align.group(1) == "LEFT":
            ids.add(m.group(1))
    return ids


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    try:
        header, sections = load(sys.argv[1])
    except (OSError, KeyError, zipfile.BadZipFile) as e:
        print(f"ERROR: {e}")
        return 2
    left = left_ids(header)
    hits = []
    for sec in sections:
        # innermost paragraphs only: a <hp:p> span holding no nested <hp:p>
        for m in re.finditer(r'<hp:p [^>]*paraPrIDRef="(\d+)"[^>]*>((?:(?!<hp:p ).)*?)</hp:p>', sec, flags=re.S):
            text = "".join(re.findall(r"<hp:t>(.*?)</hp:t>", m.group(2), flags=re.S)).strip()
            if text and m.group(1) in left:
                hits.append((m.group(1), text))
    if not hits:
        print("OK: no left-aligned text paragraph")
        return 0
    print(f"FAIL: {len(hits)} left-aligned text paragraph(s)")
    for pid, text in hits:
        print(f"  paraPr {pid}: {text[:50]}")
    return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
