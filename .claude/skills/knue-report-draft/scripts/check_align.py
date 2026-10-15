"""Fail when an hwpx has left-aligned body text outside tables and page/drawing containers.

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
import xml.etree.ElementTree as ET
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
    if not sections:
        raise ValueError("No document sections found")
    ET.fromstring(header)
    for section in sections:
        ET.fromstring(section)
    return header, sections


def left_ids(header):
    ids = set()
    for paragraph in ET.fromstring(header).iter():
        if paragraph.tag.rsplit('}', 1)[-1] != 'paraPr':
            continue
        for align in paragraph:
            if align.tag.rsplit('}', 1)[-1] == 'align' and align.get('horizontal') == 'LEFT':
                ids.add(paragraph.get('id'))
    return ids


def paragraph_text(node):
    """Collect this paragraph's text without attributing nested table paragraphs to it."""
    parts = []
    for child in node:
        name = child.tag.rsplit('}', 1)[-1]
        if name == 'p':
            continue
        if name == 't':
            parts.append(''.join(child.itertext()))
        else:
            parts.append(paragraph_text(child))
    return ''.join(parts)


def body_paragraphs(node):
    """Table cells keep their own layout; inspect body paragraphs only."""
    if node.tag.rsplit('}', 1)[-1] in {'tbl', 'tc', 'header', 'footer', 'subList', 'drawText'}:
        return
    if node.tag.rsplit('}', 1)[-1] == 'p':
        yield node
    for child in node:
        yield from body_paragraphs(child)


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    try:
        header, sections = load(sys.argv[1])
    except (OSError, KeyError, ValueError, ET.ParseError, zipfile.BadZipFile) as e:
        print(f"ERROR: {e}")
        return 2
    left = left_ids(header)
    hits = []
    for sec in sections:
        for paragraph in body_paragraphs(ET.fromstring(sec)):
            text = paragraph_text(paragraph).strip()
            pid = paragraph.get('paraPrIDRef')
            if text and pid in left:
                hits.append((pid, text))
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
