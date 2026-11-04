#!/usr/bin/env python3
"""심의자료 원본 hwpx 사본에 한글 메모(MEMO 필드)를 달아 간사가 점검할 위치를 표시한다.

사용:
    python3 annotate_memo.py <원본.hwpx> <출력.hwpx> <memos.json>
    python3 annotate_memo.py --json <원본.hwpx> <출력.hwpx> <memos.json>

memos.json — 배열. 각 항목:
    {"anchor": "보안관리", "text": "[A-1] 확인: …\\n근거: …", "occurrence": 1}
    anchor      메모를 붙일 본문 문구 (한 <hp:t> 안에 그대로 있어야 한다)
    text        메모 내용. 줄바꿈(\\n)은 메모 안 문단으로 나뉜다
    occurrence  같은 문구가 여러 번 나올 때 몇 번째인지 (기본 1)

종료코드
    0  모든 메모를 붙임
    1  일부 메모를 못 붙임 (NOT_FOUND / UNSAFE) — 붙인 것만 저장됨. 문구를 고쳐 다시 돌린다
    2  입력 오류 (원본=출력, 출력 파일 이미 존재, JSON 형식 오류 등) — 아무것도 쓰지 않음

실측으로 확인한 OWPML 규칙 (한글 2020+ 로드 기준)
    - 메모 = 본문 run 안의 `<hp:ctrl><hp:fieldBegin type="MEMO">` … 문구 … `<hp:fieldEnd>`.
      메모 내용은 fieldBegin의 `<hp:subList>` 문단이다.
    - 필드 컨트롤 하나가 글자 8자리를 차지한다. 컨트롤 뒤에서 시작하는 줄의
      `<hp:lineseg textpos>`를 8씩 밀지 않으면 그 문단이 줄바꿈에 걸친 경우 한글이 문서를 못 연다.
    - linesegarray를 지우면 (메모가 없어도) 한글이 문서를 못 연다 — 지우지 말고 보정만 한다.
    - header `<hh:memoProperties>`가 없으면 추가하고 secPr `memoShapeIDRef`를 그 id로 맞춘다.

안전 정책
    - 원본을 절대 덮어쓰지 않는다 (출력 경로가 원본이거나 이미 있으면 종료코드 2).
    - 문단에서 문구 앞에 순수 텍스트 외 요소(표·탭·다른 컨트롤)가 있으면 글자 위치를
      정확히 셀 수 없다. 이때 문단이 한 줄이면 보정이 필요 없어 붙이고, 여러 줄이면 UNSAFE로 건너뛴다.
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape, unescape

CTRL_WIDTH = 8
AUTHOR = "사전검토"
MEMO_PR = ('<hh:memoProperties itemCnt="1"><hh:memoPr id="1" width="15591" lineWidth="1" '
           'lineType="SOLID" lineColor="#B6D7AE" fillColor="#F0FFE9" activeColor="#CFF1C7" '
           'memoType="NOMAL"/></hh:memoProperties>')
P_TAG = re.compile(r'<hp:p\s[^>]*>|</hp:p>')
PURE_TEXT = re.compile(r'<hp:run\b[^>]*>|</hp:run>|<hp:t>[^<]*</hp:t>|<hp:t/>')
MEMO_BLOCK = re.compile(r'<hp:fieldBegin\b[^>]*type="MEMO".*?</hp:fieldBegin>', re.S)


def header_memo_setup(header: str) -> tuple[str, str, str, str]:
    """Return (header, memoPr id, memo style id, memo charPr id)."""
    m = re.search(r'<hh:memoPr id="(\d+)"', header)
    if m:
        memo_id = m.group(1)
    else:
        memo_id = "1"
        header = header.replace('</hh:refList>', MEMO_PR + '</hh:refList>', 1)
    st = re.search(r'<hh:style id="(\d+)" type="PARA" name="메모"[^>]*charPrIDRef="(\d+)"', header)
    style_id, char_id = (st.group(1), st.group(2)) if st else ("0", "0")
    return header, memo_id, style_id, char_id


def memo_ctrl(number: int, text: str, style_id: str, char_id: str) -> tuple[str, str]:
    bid = random.randint(10**9, 2**31 - 1)
    fid = random.randint(10**8, 10**9 - 1)
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    paras = ''.join(
        f'<hp:p id="0" paraPrIDRef="0" styleIDRef="{style_id}" pageBreak="0" columnBreak="0" merged="0">'
        f'<hp:run charPrIDRef="{char_id}"><hp:t>{escape(line)}</hp:t></hp:run></hp:p>'
        for line in text.split('\n'))
    begin = (
        f'<hp:ctrl><hp:fieldBegin id="{bid}" type="MEMO" name="" editable="1" dirty="1" '
        f'zorder="{number}" fieldid="{fid}"><hp:parameters cnt="7" name="">'
        f'<hp:integerParam name="Prop">0</hp:integerParam>'
        f'<hp:stringParam name="Command">MEMO/65535/1/0/0/{AUTHOR}/\\;;</hp:stringParam>'
        f'<hp:stringParam name="ID">memo{number}</hp:stringParam>'
        f'<hp:integerParam name="Number">{number}</hp:integerParam>'
        f'<hp:stringParam name="Author">{AUTHOR}</hp:stringParam>'
        f'<hp:stringParam name="MemoShapeIDRef">65535</hp:stringParam>'
        f'<hp:stringParam name="CreateDateTime">{now}</hp:stringParam></hp:parameters>'
        f'<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" vertAlign="TOP" '
        f'linkListIDRef="0" linkListNextIDRef="0" textWidth="0" textHeight="0" hasTextRef="0" '
        f'hasNumRef="0">{paras}</hp:subList></hp:fieldBegin></hp:ctrl>')
    end = f'<hp:ctrl><hp:fieldEnd beginIDRef="{bid}" fieldid="{fid}"/></hp:ctrl>'
    return begin, end


def enclosing_paragraph(xml: str, pos: int) -> tuple[int, int, int]:
    """Return (start of <hp:p>, end of that open tag, start of its </hp:p>) for pos."""
    stack: list[re.Match] = []
    for m in P_TAG.finditer(xml):
        if m.start() >= pos:
            break
        if m.group(0) == '</hp:p>':
            stack.pop()
        else:
            stack.append(m)
    if not stack:
        raise ValueError('anchor is not inside a paragraph')
    open_tag = stack[-1]
    depth = 0
    for m in P_TAG.finditer(xml, open_tag.start()):
        depth += -1 if m.group(0) == '</hp:p>' else 1
        if depth == 0:
            return open_tag.start(), open_tag.end(), m.start()
    raise ValueError('unclosed paragraph')


def anchor_matches(xml: str, anchor: str) -> list[re.Match]:
    """Plain <hp:t> runs containing anchor, excluding text inside existing memo bodies."""
    memo_spans = [m.span() for m in MEMO_BLOCK.finditer(xml)]
    pat = re.compile(r'<hp:t>([^<]*?)' + re.escape(escape(anchor)) + r'([^<]*?)</hp:t>')
    return [m for m in pat.finditer(xml) if not any(a <= m.start() < b for a, b in memo_spans)]


def find_anchor(xml: str, anchor: str, occurrence: int) -> re.Match | None:
    hits = anchor_matches(xml, anchor)
    return hits[occurrence - 1] if 0 < occurrence <= len(hits) else None


def insert_memo(xml: str, anchor: str, text: str, number: int,
                style_id: str, char_id: str, occurrence: int = 1) -> tuple[str, str]:
    """Return (new xml, status) where status is OK / NOT_FOUND / UNSAFE."""
    tm = find_anchor(xml, anchor, occurrence)
    if not tm:
        return xml, 'NOT_FOUND'
    _, p_body, p_close = enclosing_paragraph(xml, tm.start())
    seg_s = xml.rfind('<hp:linesegarray>', p_body, p_close)
    own_seg = seg_s != -1 and xml[seg_s:p_close].endswith('</hp:linesegarray>')
    prefix = xml[p_body:tm.start()]
    pure = PURE_TEXT.sub('', prefix) == ''
    seg_count = xml[seg_s:p_close].count('<hp:lineseg ') if own_seg else 0
    if not pure and seg_count > 1:
        return xml, 'UNSAFE'

    off_b = (sum(len(unescape(t)) for t in re.findall(r'<hp:t>([^<]*)</hp:t>', prefix))
             + len(unescape(tm.group(1))))
    off_e = off_b + len(anchor)
    begin, end = memo_ctrl(number, text, style_id, char_id)
    repl = (f'<hp:t>{tm.group(1)}</hp:t>{begin}<hp:t>{escape(anchor)}</hp:t>{end}'
            f'<hp:t>{tm.group(2)}</hp:t>')
    delta = len(repl) - (tm.end() - tm.start())
    xml = xml[:tm.start()] + repl + xml[tm.end():]
    if own_seg and seg_count > 1:
        seg_s += delta
        seg_e = p_close + delta

        def shift(m: re.Match) -> str:
            p = int(m.group(1))
            return f'textpos="{p + CTRL_WIDTH * (p > off_b) + CTRL_WIDTH * (p > off_e)}"'
        xml = xml[:seg_s] + re.sub(r'textpos="(\d+)"', shift, xml[seg_s:seg_e]) + xml[seg_e:]
    return xml, 'OK'


def annotate(src: Path, out: Path, memos: list[dict]) -> list[dict]:
    with zipfile.ZipFile(src) as zin:
        entries = [(i.filename, i.date_time, zin.read(i.filename)) for i in zin.infolist()]
    files = {name: data for name, _, data in entries}
    header, memo_id, style_id, char_id = header_memo_setup(files['Contents/header.xml'].decode('utf-8'))
    sections = sorted(n for n in files if re.fullmatch(r'Contents/section\d+\.xml', n))
    xml = {n: files[n].decode('utf-8') for n in sections}

    results = []
    number = 0
    for memo in memos:
        anchor, text, occ = memo['anchor'], memo['text'], int(memo.get('occurrence', 1))
        status = 'NOT_FOUND'
        for name in sections:  # occurrence counts across sections in order
            hits = len(anchor_matches(xml[name], anchor))
            if occ > hits:
                occ -= hits
                continue
            new, status = insert_memo(xml[name], anchor, text, number + 1, style_id, char_id, occ)
            if status == 'OK':
                number += 1
                xml[name] = new
            break
        results.append({'anchor': anchor, 'occurrence': int(memo.get('occurrence', 1)), 'status': status})

    for name in sections:
        if number:
            xml[name] = re.sub(r'memoShapeIDRef="0"', f'memoShapeIDRef="{memo_id}"', xml[name])
        files[name] = xml[name].encode('utf-8')
    if number:
        files['Contents/header.xml'] = header.encode('utf-8')

    with zipfile.ZipFile(out, 'w') as zout:
        for name, date_time, _ in entries:
            info = zipfile.ZipInfo(name, date_time)
            info.compress_type = zipfile.ZIP_STORED if name == 'mimetype' else zipfile.ZIP_DEFLATED
            zout.writestr(info, files[name])
    return results


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or '').splitlines()[0])
    ap.add_argument('src', type=Path)
    ap.add_argument('out', type=Path)
    ap.add_argument('memos', type=Path)
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args(argv)

    if args.src.resolve() == args.out.resolve():
        print('ERROR: 출력 경로가 원본과 같다 — 원본은 덮어쓰지 않는다', file=sys.stderr)
        return 2
    if args.out.exists():
        print(f'ERROR: 출력 파일이 이미 있다: {args.out}', file=sys.stderr)
        return 2
    try:
        memos = json.loads(args.memos.read_text(encoding='utf-8-sig'))
        if not isinstance(memos, list) or not all('anchor' in m and 'text' in m for m in memos):
            raise ValueError('각 항목에 anchor·text가 있어야 한다')
    except (OSError, ValueError) as e:
        print(f'ERROR: memos.json — {e}', file=sys.stderr)
        return 2

    results = annotate(args.src, args.out, memos)
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for r in results:
            print(f"{r['status']:<9} {r['anchor']}" + (f" (#{r['occurrence']})" if r['occurrence'] > 1 else ''))
    return 0 if all(r['status'] == 'OK' for r in results) else 1


if __name__ == '__main__':
    sys.exit(main())
