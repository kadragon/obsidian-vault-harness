"""Render deterministic project views from the collected collaboration dataset.

Only the marked body is managed. Text outside it survives subsequent collections.
Source statements remain quotations; no project completion is inferred.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter
from pathlib import Path
from urllib.parse import quote

BEGIN = '<!-- homepage-collect:begin v1 -->'
END = '<!-- homepage-collect:end -->'
DISCLAIMER = ('사이트 분류는 제목·본문·댓글의 명칭을 자동 대조한 결과이며 확정 범위가 아님. '
              '첨부 파일명도 분류 근거에 포함. '
              '처리구분은 게시판 표시값 그대로 기록. 완료 여부·기한은 추정하지 않음.')


def cell(value):
    return str(value or '').replace('|', '\\|').replace('\n', ' ').replace('\r', '')


def snippet(value, length=240):
    text = re.sub(r'\s+', ' ', str(value or '')).strip()
    return text if len(text) <= length else text[:length] + '…'


def quoted(value):
    return '\n'.join('> ' + line for line in str(value or '').splitlines()) or '> (내용 없음)'


def date_key(value):
    """Normalize known source date delimiters without inventing time precision."""
    return str(value or '').replace('.', '-').strip()


def latest(post):
    return max([date_key(post.get('created_at', ''))] + [date_key(c.get('date', '')) for c in post.get('comments', [])])


def ordered(posts):
    return sorted(posts, key=lambda p: (latest(p), p['id']), reverse=True)


def link(post):
    return '[[사업진행-' + post['id'] + ']]'


def table(posts):
    lines = ['| 최근 기록 | 게시글 | 제목 | 게시판 처리구분 | 댓글 | 첨부 |', '|---|---|---|---|---:|---:|']
    for p in ordered(posts):
        lines.append(f"| {cell(latest(p))} | {link(p)} | {cell(p['title'])} | {cell(p.get('status') or '표시 없음')} | {len(p.get('comments', []))} | {len(p.get('attachments', []))} |")
    if not posts:
        lines.append('| — | — | 수집된 게시글 없음 | — | 0 | 0 |')
    return '\n'.join(lines)


def discussions(posts, limit=12, site=None, site_config=None):
    def relevant(comment):
        if site is None:
            return True
        text = str(comment.get('text', ''))
        mentioned = {s['name'] for s in site_config if any(alias in text for alias in [s['name'], *s.get('aliases', [])])}
        return not mentioned or site in mentioned

    comments = [(date_key(c.get('date', '')), p['id'], n, p, c)
                for p in posts for n, c in enumerate(p.get('comments', [])) if str(c.get('text', '')).strip() and relevant(c)]
    comments.sort(key=lambda row: row[:3], reverse=True)
    lines = []
    for _, _, _, p, c in comments[:limit]:
        sites = ', '.join(p.get('sites', [])) or p.get('category', '미분류')
        lines += [f"- {link(p)} · {cell(p['title'])} · {cell(sites)} · {cell(c.get('date'))} · {cell(c.get('author'))}",
                  quoted(snippet(c.get('text'))), '']
    return '\n'.join(lines).rstrip() or '수집된 댓글 없음.'


def local_link(path, note, output, name=None):
    target = (output / str(path)).resolve()
    if not target.is_relative_to(output.resolve()):
        raise ValueError(f'Attachment/source path escapes output: {path}')
    relative = os.path.relpath(target, (output / note).parent).replace('\\', '/')
    label = str(name or target.name).replace('[', '\\[').replace(']', '\\]')
    return '[' + label + '](' + quote(relative, safe='/') + ')'


def document(title, summary, sections):
    body = f'# {title}\n\n> [!abstract] 프로젝트 요약\n> {summary}\n\n## 관련\n\n- #업무/홈페이지\n\n'
    body += '\n\n'.join(f'## {heading}\n\n{content}' for heading, content in sections if content)
    return '---\ntype: project\nstatus: active\n---\n\n' + BEGIN + '\n' + body.rstrip() + '\n' + END + '\n'


def source_note(p, output, name):
    metadata = '\n'.join(f'- {label}: {value}' for label, value in [
        ('게시판', p['board']), ('글 번호', p['id']), ('작성자', p.get('author', '')),
        ('소속', p.get('department', '')), ('작성일', p.get('created_at', '')),
        ('처리구분', p.get('status') or '표시 없음'), ('사이트 자동 분류', ', '.join(p.get('sites', [])) or p.get('category', '미분류')),
        ('추가 범위', ', '.join(p.get('supplemental_sites', [])) or '표시 없음'),
        ('원문', f"[게시판 원문]({p['url']})")])
    evidence = '\n'.join('- ' + cell(e.get('site')) + ' · ' + cell(e.get('field')) +
                         (' · 근거: ' if e.get('field') == 'override' else ' · 명칭: ') + cell(e.get('alias'))
                         for e in p.get('classification_evidence', []))
    comments = []
    for n, c in enumerate(p.get('comments', []), 1):
        comments += [f"### 댓글 {n} · {cell(c.get('author'))} · {cell(c.get('date'))}", quoted(c.get('text')), '']
    attachments = []
    for a in p.get('attachments', []):
        target = local_link(a['path'], name, output, a['name']) if a.get('path') else '(원본 미수집)'
        attachments.append(f"- {target} · {a.get('size', '?')} bytes · SHA-256 `{a.get('sha256', '')}`")
    if p.get('source_html'):
        attachments.append('- ' + local_link(p['source_html'], name, output, '게시글 HTML 원본'))
    return document(p['title'], '협업 게시판 원문과 댓글 보관. ' + DISCLAIMER, [
        ('범위', metadata), ('분류 근거', evidence), ('본문 원문', quoted(p.get('body_text'))),
        ('댓글 원문', '\n\n'.join(comments).strip()), ('관련 문서', '\n'.join(attachments))])


def build_documents(dataset, config, output):
    if dataset.get('schema_version') != 1:
        raise ValueError('Unsupported dataset schema_version')
    sites = [s['name'] for s in config['sites']]
    if len(sites) != 14 or len(set(sites)) != 14:
        raise ValueError('Expected 14 distinct canonical site names')
    for site in sites:
        if re.search(r'[<>:"/\\|?*]', site) or site in {'.', '..'} or site.rstrip(' .') != site:
            raise ValueError(f'Unsafe site folder: {site}')
    posts = [dict(p, **{k: v for k, v in config.get('overrides', {}).get(p['id'], {}).items()
                       if k in {'sites', 'category', 'supplemental_sites'}}) for p in dataset['posts']]
    for post in posts:
        override = config.get('overrides', {}).get(post['id'])
        if override:
            post['classification_evidence'] = [
                {'site': site, 'field': 'override', 'alias': override.get('evidence') or site}
                for site in post.get('sites', [])]
            if not post.get('sites'):
                post['classification_evidence'] = [{'site': post.get('category', '미분류'),
                                                    'field': 'override',
                                                    'alias': override.get('evidence') or 'sites.json'}]
    ids = [p['id'] for p in posts]
    if len(set(ids)) != len(ids) or any(not re.fullmatch(r'\d+-\d+', i) for i in ids):
        raise ValueError('Post IDs must be unique board-number pairs')
    for p in posts:
        if set(p.get('sites', [])) - set(sites):
            raise ValueError(f"Unknown site in {p['id']}")
    result = {}
    for p in posts:
        name = Path('원문노트') / f"사업진행-{p['id']}.md"
        result[name] = source_note(p, output, name)
    site_rows = ['| 사이트 | 관련 게시글 | 최근 기록 | 보기 |', '|---|---:|---|---|']
    for site in sites:
        selected = [p for p in posts if site in p.get('sites', [])]
        title = '_' + site + ' 사업 진행'
        result[Path('사이트별') / site / (title + '.md')] = document(site + ' 사업 진행',
            f'관련 게시글 {len(selected)}건. ' + DISCLAIMER,
            [('목표', '사이트별 요청·협의·자료를 원문과 함께 확인.'),
             ('최근 협의 · 원문 발언', discussions(selected, site=site, site_config=config['sites'])), ('범위 · 관련 게시글', table(selected)),
             ('관련 문서', '[[_사업 진행 종합]] · [[_공통 및 미분류 사업 진행]]')])
        site_rows.append(f'| {cell(site)} | {len(selected)} | {cell(max((latest(p) for p in selected), default="—"))} | [[{title}]] |')
    unclassified = [p for p in posts if not p.get('sites')]
    common = [p for p in unclassified if p.get('category') == '공통']
    supplemental = [p for p in unclassified if p.get('category') == '추가 범위']
    unknown = [p for p in unclassified if p.get('category') not in {'공통', '추가 범위'}]
    result[Path('_공통 및 미분류 사업 진행.md')] = document('공통 및 미분류 사업 진행',
        f'공통 {len(common)}건 · 미분류 {len(unknown)}건 · 추가 범위 {len(supplemental)}건. ' + DISCLAIMER,
        [('공통', table(common)), ('분류 확인 필요', table(unknown)),
         ('추가 범위 · 시설물 예약', table(supplemental) if supplemental else ''),
         ('최근 협의 · 원문 발언', discussions(unclassified)), ('관련 문서', '[[_사업 진행 종합]]')])
    boards = ['| 게시판 | 원문 총 건수 | 수집 건수 |', '|---|---:|---:|']
    boards += [f"| {cell(b['name'])} | {b.get('total', '?')} | {b.get('collected', 0)} |" for b in dataset.get('boards', [])]
    states = Counter(p.get('status') or '표시 없음' for p in posts)
    status_text = '\n'.join(f'- {cell(status)}: {count}건' for status, count in sorted(states.items()))
    changes = []
    for key, label in [('new', '새 글'), ('updated', '수정 글'), ('missing', '이번 수집에서 확인 못 한 글')]:
        entries = dataset.get('changes', {}).get(key, [])
        changes += [f'- {label}: {len(entries)}건' + (' · ' + ' · '.join('[[사업진행-' + i + ']]' for i in entries) if entries else '')]
    errors = dataset.get('errors', [])
    error_text = '\n'.join('- ' + cell(e if isinstance(e, str) else json.dumps(e, ensure_ascii=False)) for e in errors)
    result[Path('_사업 진행 종합.md')] = document('통합 홈페이지 사업 진행 종합',
        f"수집 기준 {dataset['collected_at']} · 게시글 {len(posts)}건 · 댓글 {sum(len(p.get('comments', [])) for p in posts)}건 · 첨부 {sum(len(p.get('attachments', [])) for p in posts)}건.",
        [('목표', '14개 사이트의 요청·협의·처리구분을 원문과 함께 확인.'),
         ('범위', DISCLAIMER + '\n\n다중 사이트 글은 각 보기에 연결하며 원문노트는 한 번만 저장. 사이트별 건수 합계는 전체 글 수와 다를 수 있음.'),
         ('최근 협의 · 확인할 원문 발언', discussions(posts, 20)),
         ('사이트별 현황', '\n'.join(site_rows)), ('공통 및 분류 확인', f'공통 {len(common)}건 · 미분류 {len(unknown)}건 · 추가 범위 {len(supplemental)}건 · [[_공통 및 미분류 사업 진행]]'),
         ('게시판별 수집 현황', '\n'.join(boards)), ('게시판 처리구분', status_text),
         ('이번 수집 변경', '\n'.join(changes)), ('수집 오류 · 확인 필요', error_text),
         ('최근 게시글', table(ordered(posts)[:20]))])
    return result


def render(output, config, dataset=None):
    """Preflight all collisions, then write only changed managed notes."""
    output = Path(output)
    if isinstance(config, (str, Path)):
        config = json.loads(Path(config).read_text(encoding='utf-8'))
    if dataset is None:
        dataset = json.loads((output / '원본데이터' / 'dataset.json').read_text(encoding='utf-8'))
    documents = build_documents(dataset, config, output)
    writes = []
    report = {'created': 0, 'updated': 0, 'unchanged': 0, 'files': []}
    for relative, generated in documents.items():
        path = output / relative
        if not path.resolve().is_relative_to(output.resolve()):
            raise ValueError(f'Note path escapes output: {relative}')
        exists = path.exists()
        content = generated
        if exists:
            original = path.read_text(encoding='utf-8')
            if original.count(BEGIN) != 1 or original.count(END) != 1 or original.index(BEGIN) >= original.index(END):
                raise ValueError(f'Refusing unmanaged/corrupt existing note: {path}')
            content = original[:original.index(BEGIN)] + generated[generated.index(BEGIN):generated.index(END) + len(END)] + original[original.index(END) + len(END):]
            if content == original:
                report['unchanged'] += 1
                report['files'].append(str(path))
                continue
        writes.append((path, content))
        report['updated' if exists else 'created'] += 1
        report['files'].append(str(path))
    for path, content in writes:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix('.md.homepage-tmp')
        temporary.write_text(content, encoding='utf-8', newline='\n')
        temporary.replace(path)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--config', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(render(args.output, args.config), ensure_ascii=False))


if __name__ == '__main__':
    main()
