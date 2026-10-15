"""Collect authenticated newknue boards; credentials and cookies stay in memory."""
from __future__ import annotations

import argparse
import hashlib
import http.cookiejar
import json
import os
from pathlib import Path
import re
import sys
import time
import unicodedata
from datetime import datetime, timezone, timedelta
import urllib.error
import urllib.parse
import urllib.request

from bs4 import BeautifulSoup
from classification import apply_override

BASE = 'https://cop.hanshinit.co.kr'
BOARDS = [(2695, 3774, '업무협의(소통공간)'), (2696, 3775, '주간 및 월간보고'), (2697, 3776, '자료실')]
DEFAULT_OUTPUT = Path('12_Projects/2026/통합 홈페이지/10. 사업 진행 정보')
ALLOWED = {'loginForm.do', 'login.do', 'index.do', 'sub.do', 'selectBbsNttList.do', 'selectBbsNttView.do', 'downloadBbsFile.do'}


class CollectionError(Exception):
    pass


def nfc(value):
    return unicodedata.normalize('NFC', value)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def post_hash(post):
    # Archive layout is storage metadata, not a business-content change.
    return digest(json_bytes({k: v for k, v in post.items() if k not in {'content_hash', 'source_html'}}))


def source_hash(post):
    """Detect board edits independently of local classification and archive layout."""
    fields = ('id', 'bbs_no', 'ntt_no', 'board', 'title', 'author', 'department',
              'status', 'created_at', 'body_text', 'body_html', 'comments')
    content = {key: post.get(key) for key in fields}
    content['attachments'] = [{key: a.get(key) for key in ('id', 'name', 'sha256', 'size')}
                              for a in post.get('attachments', [])]
    return digest(json_bytes(content))


def write_changed(path, data):
    if path.exists() and path.read_bytes() == data:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.part')
    temporary.write_bytes(data)
    temporary.replace(path)
    return True


def read_env(path):
    values = {}
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('export '):
            line = line[7:]
        key, sep, value = line.partition('=')
        if sep:
            values[key.strip()] = value.strip().strip('\"\'')
    keys = ['HANSHIN_COP_ID', 'HANSHIN_COP_PW']
    if any(not values.get(key) for key in keys):
        raise CollectionError('Missing required .env credential keys')
    return {key: values[key] for key in keys}


def safe_url(url):
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != 'https' or parsed.netloc != 'cop.hanshinit.co.kr'
            or parsed.path != '/newknue/' + parsed.path.rsplit('/', 1)[-1]
            or parsed.path.rsplit('/', 1)[-1] not in ALLOWED):
        raise CollectionError('Unexpected request destination or action: ' + parsed.netloc + parsed.path)
    return urllib.parse.urlunsplit(parsed._replace(fragment=''))


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        safe_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Client:
    def __init__(self, delay=0.35):
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()), SafeRedirect())
        self.delay = delay
        self.last = 0

    def open(self, url, data=None):
        safe_url(url)
        time.sleep(max(0, self.delay - (time.monotonic() - self.last)))
        self.last = time.monotonic()
        request = urllib.request.Request(url, data=data, headers={'User-Agent': 'KNUE-project-collector/1.0'})
        return self.opener.open(request, timeout=90)

    def html(self, url, data=None, authenticated=True):
        with self.open(url, data) as response:
            raw = response.read()
        soup = BeautifulSoup(raw.decode('utf-8'), 'html.parser')
        if authenticated and not soup.select_one('a[href*="logout.do"]'):
            raise CollectionError('Session expired or authentication failed')
        return soup

    def login(self, env):
        self.html(BASE + '/newknue/loginForm.do', authenticated=False)
        payload = urllib.parse.urlencode({'id': env['HANSHIN_COP_ID'],
                                         'password': env['HANSHIN_COP_PW'], 'rurl': ''}).encode()
        self.html(BASE + '/newknue/login.do', payload)


def clean_text(node, multiline=False):
    if node is None:
        return ''
    copy = BeautifulSoup(str(node), 'html.parser')
    for element in copy.select('script, style, .bbs_ico, button, form'):
        element.decompose()
    if multiline:
        for br in copy.find_all('br'):
            br.replace_with('\n')
        for element in copy.select('p, div, tr, li'):
            element.insert_after('\n')
        lines = [' '.join(line.split()) for line in copy.get_text().splitlines()]
        return '\n'.join(line for line in lines if line).strip()
    return ' '.join(copy.get_text(' ', strip=True).split())


def listing(soup, board, key):
    count = soup.select_one('.bbsCount')
    match = re.search(r'총\s*게시물\s*([\d,]+).*?페이지\s*\d+\s*/\s*(\d+)', clean_text(count))
    if not match:
        raise CollectionError(f'Unrecognized list count: board {board}')
    total, pages = int(match[1].replace(',', '')), int(match[2])
    rows = []
    for row in soup.select('table.list tbody tr'):
        link = row.select_one('td.subject a[href*="selectBbsNttView.do"]')
        if not link:
            continue
        params = urllib.parse.parse_qs(urllib.parse.urlsplit(link['href']).query)
        ntt = int(params['nttNo'][0])
        if int(params['bbsNo'][0]) != board:
            raise CollectionError('Unexpected board in list entry')
        comments = row.select_one('.bbs_comment')
        match = re.search(r'(\d+)\s*$', clean_text(comments))
        rows.append({'ntt': ntt, 'expected_comments': int(match[1]) if match else 0})
    return total, pages, rows


def parse_post(soup, board, key, name, ntt):
    table = soup.select_one('table.view')
    reply = soup.select_one('#bbsNttComment')
    if table is None or reply is None:
        raise CollectionError(f'Missing post or comment section: {board}-{ntt}')
    fields = {}
    for row in table.select('tr'):
        th, td = row.find('th'), row.find('td')
        if th and td:
            fields[clean_text(th)] = td
    if not {'제목', '내용', '작성자', '부서', '처리구분'} <= fields.keys():
        raise CollectionError(f'Unrecognized post fields: {board}-{ntt}')
    created = clean_text(soup.select_one('.bbsInfo .bbsCount'))
    date = re.search(r'(\d{4})년\s*(\d{2})월\s*(\d{2})일\s*(\d{2})시\s*(\d{2})분\s*(\d{2})초', created)
    if not date:
        raise CollectionError(f'Missing source timestamp: {board}-{ntt}')
    created = '{}-{}-{} {}:{}:{}'.format(*date.groups())
    attachments = []
    for a in table.select('ul.attach a[href]'):
        url = safe_url(urllib.parse.urljoin(BASE, a['href']))
        params = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
        if 'atchmnflNo' not in params:
            raise CollectionError('Unrecognized attachment identifier')
        if not re.fullmatch(r'[0-9]+', params['atchmnflNo'][0]):
            raise CollectionError('Attachment identifier must be numeric')
        attachments.append({'id': params['atchmnflNo'][0], 'name': clean_text(a), 'url': url})
    comments = []
    for li in reply.select('ul > li'):
        body = li.select_one('.bbsReplyText')
        if body is None:
            raise CollectionError('Unrecognized comment structure')
        comments.append({'author': clean_text(li.select_one('.name')),
                         'date': clean_text(li.select_one('.date')),
                         'text': clean_text(body, multiline=True)})
    count = re.search(r'(\d+)\s*개', clean_text(reply.select_one('.bbsReplyCount')))
    if not count or int(count[1]) != len(comments):
        raise CollectionError(f'Comment count mismatch: {board}-{ntt}')
    # Archive content only: omit authentication UI, forms, scripts and mutation controls.
    stable_info = '<div class="bbsInfo"><div class="bbsCount">작성일 ' + date.group(0) + '</div></div>'
    archive = BeautifulSoup(stable_info + str(table) + str(reply), 'html.parser')
    for element in archive.select('script, style, form, button, .bbs_ico'):
        element.decompose()
    post = {'id': f'{board}-{ntt}', 'bbs_no': board, 'ntt_no': ntt, 'board': name,
            'title': clean_text(fields['제목']), 'author': clean_text(fields['작성자']),
            'department': clean_text(fields['부서']), 'status': clean_text(fields['처리구분']),
            'created_at': created, 'body_text': clean_text(fields['내용'], multiline=True),
            'body_html': str(fields['내용']), 'comments': comments, 'attachments': attachments,
            'url': f'{BASE}/newknue/selectBbsNttView.do?key={key}&bbsNo={board}&nttNo={ntt}'}
    return post, str(archive).encode('utf-8')


def classify(post, config):
    # Department is sender metadata, not evidence of the target site.
    fields = {'title': post['title'], 'body': post['body_text'],
              'comments': '\n'.join(c['text'] for c in post['comments']),
              'attachments': '\n'.join(a['name'] for a in post['attachments'])}
    evidence = []
    sites = []
    for site in config['sites']:
        for field, text in fields.items():
            aliases = [alias for alias in site['aliases'] if nfc(alias).casefold() in nfc(text).casefold()]
            if aliases:
                evidence.append({'site': site['name'], 'field': field, 'alias': aliases[0]})
        if any(e['site'] == site['name'] for e in evidence):
            sites.append(site['name'])
    if sites:
        category = '사이트별'
    else:
        common_terms = ['주간보고', '월간보고', '회의록', '현행프로그램', '현행게시판',
                        '킥오프', '착수', '전체', '공통', '통합 홈페이지', '통합홈페이지', '사이트키']
        category = '공통' if post['bbs_no'] == 2696 or any(t in fields['title'] for t in common_terms) else '미분류'
    post.update(sites=sites, classification_evidence=evidence, category=category)
    apply_override(post, config)


def safe_filename(name, max_bytes=220):
    name = nfc(re.sub(r'[<>:"/\\|?*\x00-\x1f\[\]#^]', '_', name)).strip(' .')
    suffix = Path(name).suffix
    stem = name[:-len(suffix)] if suffix else name
    suffix = suffix[:12]
    stem = stem.encode('utf-8')[:max_bytes - len(suffix.encode('utf-8'))].decode('utf-8', errors='ignore')
    return (stem or 'attachment') + suffix


def download(client, attachment, postid, root):
    if not re.fullmatch(r'[0-9]+', str(attachment['id'])) or not re.fullmatch(r'[0-9]+-[0-9]+', postid):
        raise CollectionError('Invalid post or attachment identifier')
    folder = root / '첨부파일' / postid
    if not folder.resolve().is_relative_to(root.resolve()):
        raise CollectionError('Attachment destination escapes output')
    folder.mkdir(parents=True, exist_ok=True)
    temporary = folder / f'{attachment["id"]}.part'
    sha = hashlib.sha256()
    size = 0
    try:
        with client.open(attachment['url']) as response, temporary.open('wb') as output:
            if urllib.parse.urlsplit(response.url).path.endswith('loginForm.do'):
                raise CollectionError('Attachment redirected to login')
            declared_size = response.headers.get('Content-Length')
            if response.headers.get('Content-Type', '').split(';', 1)[0].strip().lower() == 'text/html':
                raise CollectionError('Unexpected HTML instead of attachment')
            first = True
            while chunk := response.read(1024 * 1024):
                if first:
                    beginning = chunk[:4096].removeprefix(b'\xef\xbb\xbf').lower().lstrip()
                    if beginning.startswith((b'<!doctype html', b'<html', b'<script')):
                        raise CollectionError('Unexpected HTML instead of attachment')
                    first = False
                output.write(chunk)
                sha.update(chunk)
                size += len(chunk)
            if size == 0 or (declared_size and size != int(declared_size)):
                raise CollectionError('Empty or truncated attachment')
        checksum = sha.hexdigest()
        prefix = f'{attachment["id"]}-{checksum[:12]}-'
        filename = safe_filename(attachment['name'], max_bytes=240 - len(prefix.encode('utf-8')))
        destination = folder / (prefix + filename)
        if destination.exists():
            if digest(destination.read_bytes()) != checksum:
                raise CollectionError('Existing attachment hash mismatch')
            temporary.unlink()
        else:
            temporary.replace(destination)
        attachment.update(path=destination.relative_to(root).as_posix(), sha256=checksum, size=size)
    finally:
        if temporary.exists():
            temporary.unlink()


def collect(root, config, client, previous=None):
    posts, boards = [], []
    for board, key, name in BOARDS:
        print(f'Collecting board {board}', flush=True)
        url = f'{BASE}/newknue/selectBbsNttList.do?bbsNo={board}&key={key}'
        total, pages, rows = listing(client.html(url), board, key)
        indexed = {row['ntt']: row for row in rows}
        for page in range(2, pages + 1):
            other_total, _, more = listing(client.html(url + f'&pageIndex={page}'), board, key)
            if other_total != total:
                raise CollectionError('Board changed during pagination; rerun collection')
            indexed.update({row['ntt']: row for row in more})
        if len(indexed) != total:
            raise CollectionError(f'Board {board} count mismatch: expected {total}, found {len(indexed)}')
        for ntt, row in indexed.items():
            url = f'{BASE}/newknue/selectBbsNttView.do?bbsNo={board}&key={key}&nttNo={ntt}'
            post, archive = parse_post(client.html(url), board, key, name, ntt)
            if len(post['comments']) != row['expected_comments']:
                raise CollectionError(f'Comments changed during collection: {post["id"]}; rerun')
            for attachment in post['attachments']:
                download(client, attachment, post['id'], root)
            classify(post, config)
            html_path = Path('원본데이터') / '게시글' / post['id'] / (digest(archive) + '.html')
            write_changed(root / html_path, archive)
            post['source_html'] = html_path.as_posix()
            post['content_hash'] = post_hash(post)
            snapshot = html_path.with_suffix('.json')
            # JSON snapshot version includes attachment/classification changes as well as HTML.
            snapshot = snapshot.with_name(post['content_hash'] + '.json')
            write_changed(root / snapshot, json_bytes(post))
            posts.append(post)
            print(f'  {post["id"]}: {len(post["comments"])} comments, {len(post["attachments"])} attachments', flush=True)
        boards.append({'id': board, 'key': key, 'name': name, 'total': total, 'collected': len(indexed)})
    old = {post['id']: post for post in (previous or {}).get('posts', [])}
    now = {post['id']: post for post in posts}
    changes = {'new': sorted(now.keys() - old.keys()),
               'updated': sorted(p for p in now.keys() & old.keys() if source_hash(now[p]) != source_hash(old[p])),
               'missing': sorted(old.keys() - now.keys())}
    dataset = {'schema_version': 1,
               'collected_at': datetime.now(timezone(timedelta(hours=9))).isoformat(timespec='seconds'),
               'boards': boards, 'posts': posts, 'changes': changes, 'errors': []}
    verify_data(root, dataset)
    write_changed(root / '원본데이터' / 'dataset.json', json_bytes(dataset))
    return dataset


def verify(root):
    data = json.loads((root / '원본데이터' / 'dataset.json').read_text(encoding='utf-8'))
    return verify_data(root, data)


def verify_data(root, data):
    ids = [p['id'] for p in data['posts']]
    if len(ids) != len(set(ids)):
        raise CollectionError('Duplicate post IDs')
    for board in data['boards']:
        if sum(p['bbs_no'] == board['id'] for p in data['posts']) != board['total']:
            raise CollectionError('Stored board totals do not reconcile')
    files = 0
    for post in data['posts']:
        archive = (root / post['source_html']).resolve()
        if not archive.is_relative_to(root.resolve()) or not archive.is_file():
            raise CollectionError('Missing archived post HTML')
        if digest(archive.read_bytes()) != archive.stem:
            raise CollectionError('Archived post HTML hash mismatch')
        if post_hash(post) != post['content_hash']:
            raise CollectionError('Post content hash mismatch')
        for attachment in post['attachments']:
            path = (root / attachment['path']).resolve()
            if not path.is_relative_to(root.resolve()):
                raise CollectionError('Attachment path escapes output')
            if not path.is_file() or path.stat().st_size != attachment['size'] or digest(path.read_bytes()) != attachment['sha256']:
                raise CollectionError(f'Attachment integrity failure: {post["id"]}')
            files += 1
    print(json.dumps({'posts': len(ids), 'comments': sum(len(p['comments']) for p in data['posts']),
                      'attachments': files, 'integrity': 'PASS'}, ensure_ascii=False))
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vault', type=Path, default=Path.cwd())
    parser.add_argument('--output', type=Path)
    parser.add_argument('--env', type=Path)
    parser.add_argument('--config', type=Path, default=Path(__file__).resolve().parents[1] / 'references' / 'sites.json')
    parser.add_argument('--delay', type=float, default=0.35)
    parser.add_argument('--verify', action='store_true', help='Offline integrity check only')
    args = parser.parse_args()
    root = (args.output or args.vault / DEFAULT_OUTPUT).resolve()
    if args.verify:
        verify(root)
        return
    config = json.loads(args.config.read_text(encoding='utf-8'))
    canonical = [s['name'] for s in config['sites']]
    if len(canonical) != 14 or len(set(canonical)) != 14:
        raise CollectionError('Expected 14 unique canonical sites')
    dataset_path = root / '원본데이터' / 'dataset.json'
    previous = json.loads(dataset_path.read_text(encoding='utf-8')) if dataset_path.exists() else None
    root.mkdir(parents=True, exist_ok=True)
    # Exclusive lock prevents concurrent refresh from mixing versions or temporary files.
    lock = root / '.collection.lock'
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise CollectionError('Collection lock exists; check running process before removing it')
    try:
        os.close(descriptor)
        client = Client(max(0.1, args.delay))
        credentials = read_env(args.env or args.vault / '.env')
        client.login(credentials)
        credentials.clear()
        data = collect(root, config, client, previous)
        verify(root)
        print(json.dumps({'changes': data['changes']}, ensure_ascii=False))
    finally:
        lock.unlink()


if __name__ == '__main__':
    try:
        main()
    except (CollectionError, urllib.error.URLError, OSError, ValueError, KeyError) as exc:
        # Never print request payloads, response bodies or arbitrary exception values.
        message = str(exc) if isinstance(exc, CollectionError) else type(exc).__name__
        print('Collection failed: ' + message, file=sys.stderr)
        sys.exit(1)
