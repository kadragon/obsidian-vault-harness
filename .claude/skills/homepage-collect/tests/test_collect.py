"""Offline collection contracts using local source-shaped fixtures and fake IO."""
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import collect
from bs4 import BeautifulSoup


VIEW = '''<a href="logout.do">Logout</a><div class="bbsInfo"><div class="bbsCount">작성일 2026년 10월 01일 10시 20분 30초</div></div>
<table class="view"><tr><th>처리구분</th><td>진행중</td></tr><tr><th>작성자</th><td>작성자</td></tr><tr><th>부서</th><td>정보전산원</td></tr>
<tr><th>제목</th><td>인권센터 요청<span class="bbs_ico">새글</span></td></tr><tr><th>내용</th><td>인권센터<br>둘째 줄</td></tr>
<tr><th>파일</th><td><ul class="attach"><li><a href="/newknue/downloadBbsFile.do?atchmnflNo=1">요청.pdf</a></li></ul></td></tr></table>
<div id="bbsNttComment"><div class="bbsReplyCount">총 1개의 댓글</div><ul><li><span class="name">담당자</span><span class="date">2026.10.02</span>
<button onclick="delete()">삭제</button><div class="bbsReplyText">확인<br>다음 줄</div></li></ul></div>'''


class Response(io.BytesIO):
    url = collect.BASE + '/newknue/downloadBbsFile.do?atchmnflNo=1'
    def __init__(self, content, declared=None):
        super().__init__(content)
        self.headers = {'Content-Length': str(len(content) if declared is None else declared)}


class FakeClient:
    def __init__(self):
        self.content = b'%PDF-1.7 original'
        self.view = VIEW
    def open(self, url):
        return Response(self.content)
    def html(self, url):
        if 'selectBbsNttView.do' in url:
            return BeautifulSoup(self.view, 'html.parser')
        return BeautifulSoup('''<div class="bbsCount">총 게시물 1 개, 페이지 1 / 1</div><table class="list"><tbody><tr><td class="subject"><a href="selectBbsNttView.do?bbsNo=2695&nttNo=1">title</a><span class="bbs_comment">댓글수 : 1</span></td></tr></tbody></table>''', 'html.parser')


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.config = {'sites': [{'name': '인권센터', 'aliases': ['인권센터']},
                                 {'name': '정보전산원', 'aliases': ['정보전산원']}], 'overrides': {}}
    def tearDown(self):
        self.temp.cleanup()

    def test_login_intermediates_allowed_mutations_and_other_hosts_denied(self):
        for name in ('index.do', 'sub.do', 'selectBbsNttList.do'):
            self.assertEqual(collect.safe_url(collect.BASE + '/newknue/' + name), collect.BASE + '/newknue/' + name)
        for url in ('https://evil.example/newknue/login.do', collect.BASE + '/newknue/deleteBbsNtt.do', 'http://cop.hanshinit.co.kr/newknue/login.do'):
            with self.assertRaises(collect.CollectionError):
                collect.safe_url(url)

    def test_parse_preserves_lines_comments_but_not_controls(self):
        post, archive = collect.parse_post(BeautifulSoup(VIEW, 'html.parser'), 2695, 3774, 'board', 1)
        self.assertEqual(post['title'], '인권센터 요청')
        self.assertEqual(post['body_text'], '인권센터\n둘째 줄')
        self.assertEqual(post['comments'][0]['text'], '확인\n다음 줄')
        self.assertNotIn(b'button', archive)
        self.assertIn('2026년 10월 01일 10시 20분 30초'.encode(), archive)
        collect.classify(post, self.config)
        self.assertEqual(post['sites'], ['인권센터'])

    def test_reply_count_mismatch_fails(self):
        with self.assertRaises(collect.CollectionError):
            collect.parse_post(BeautifulSoup(VIEW.replace('총 1개', '총 2개'), 'html.parser'), 2695, 3774, 'board', 1)

    def test_refresh_idempotent_and_same_id_attachment_replacement_detected(self):
        client = FakeClient()
        with patch.object(collect, 'BOARDS', [(2695, 3774, 'board')]):
            first = collect.collect(self.root, self.config, client)
            second = collect.collect(self.root, self.config, client, first)
            self.assertEqual(second['changes'], {'new': [], 'updated': [], 'missing': []})
            self.assertEqual(len(list((self.root / '첨부파일').rglob('*.pdf'))), 1)
            client.content = b'%PDF-1.7 replaced'
            third = collect.collect(self.root, self.config, client, second)
            self.assertEqual(third['changes']['updated'], ['2695-1'])
            self.assertEqual(len(list((self.root / '첨부파일').rglob('*.pdf'))), 2)
            collect.verify(self.root)

    def test_failure_preserves_last_successful_dataset(self):
        client = FakeClient()
        with patch.object(collect, 'BOARDS', [(2695, 3774, 'board')]):
            first = collect.collect(self.root, self.config, client)
            previous = (self.root / '원본데이터/dataset.json').read_bytes()
            client.content = b'<html>Login</html>'
            with self.assertRaises(collect.CollectionError):
                collect.collect(self.root, self.config, client, first)
            self.assertEqual((self.root / '원본데이터/dataset.json').read_bytes(), previous)
            self.assertFalse(list(self.root.rglob('*.part')))

    def test_corrupted_attachment_fails_verification(self):
        client = FakeClient()
        with patch.object(collect, 'BOARDS', [(2695, 3774, 'board')]):
            data = collect.collect(self.root, self.config, client)
        (self.root / data['posts'][0]['attachments'][0]['path']).write_bytes(b'corrupt')
        with self.assertRaises(collect.CollectionError):
            collect.verify(self.root)

    def test_attachment_identifiers_cannot_escape_output(self):
        client = FakeClient()
        output = self.root / 'output'
        for bad in ('../../../outside', '/outside', '..', '1/2'):
            attachment = {'id': bad, 'name': 'file.pdf', 'url': Response.url}
            with self.assertRaises(collect.CollectionError):
                collect.download(client, attachment, '2695-1', output)
        self.assertFalse(list(self.root.rglob('*.pdf')))
        with self.assertRaises(collect.CollectionError):
            collect.parse_post(BeautifulSoup(VIEW.replace('atchmnflNo=1', 'atchmnflNo=../1'), 'html.parser'), 2695, 3774, 'board', 1)

    def test_archive_layout_is_not_business_content_change(self):
        post = {'id': '2695-1', 'title': 'Request', 'body_text': 'original', 'source_html': 'old.html'}
        updated = dict(post, source_html='new.html')
        self.assertEqual(collect.post_hash(post), collect.post_hash(updated))
        self.assertNotEqual(collect.post_hash(post), collect.post_hash(dict(updated, body_text='edited')))


if __name__ == '__main__':
    unittest.main()
