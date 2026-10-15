"""Offline renderer contracts: scope, quotations, refresh safety and collisions."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location('render_notes', Path(__file__).parents[1] / 'scripts' / 'render_notes.py')
renderer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(renderer)


class RenderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.output = Path(self.temp.name)
        self.config = {'sites': [{'name': f'사이트{i}', 'aliases': []} for i in range(14)], 'overrides': {}}
        self.data = {'schema_version': 1, 'collected_at': '2026-10-14T00:00:00Z',
                     'boards': [{'name': '업무협의', 'total': 1, 'collected': 1}],
                     'posts': [{'id': '2695-89136', 'board': '업무협의', 'title': '디자인 확인',
                                'author': '작성자', 'department': '부서', 'created_at': '2026-10-10 09:00:00',
                                'status': '진행', 'body_text': '원문 보존\n두 번째 줄',
                                'comments': [{'author': '담당자', 'date': '2026-10-13 10:00:00',
                                              'text': '수정 시안 확인 요청'}],
                                'attachments': [{'name': '시안 #1.pdf', 'path': '첨부/시안 #1.pdf',
                                                 'sha256': 'abc', 'size': 3}],
                                'sites': ['사이트0', '사이트1'], 'classification_evidence': [],
                                'url': 'https://example.org/post/89136', 'source_html': '원문/89136.html'}],
                     'changes': {'new': ['2695-89136'], 'updated': [], 'missing': []}, 'errors': []}

    def tearDown(self):
        self.temp.cleanup()

    def test_multi_site_one_source_with_comment_and_attachment(self):
        result = renderer.render(self.output, self.config, self.data)
        self.assertEqual(result['created'], 17)
        self.assertEqual(len(list((self.output / '원문노트').glob('*.md'))), 1)
        for i in (0, 1):
            text = (self.output / f'사이트별/사이트{i}/_사이트{i} 사업 진행.md').read_text(encoding='utf-8')
            self.assertIn('[[사업진행-2695-89136]]', text)
            self.assertIn('수정 시안 확인 요청', text)
            self.assertIn('2026-10-13 10:00:00', text)
        source = (self.output / '원문노트/사업진행-2695-89136.md').read_text(encoding='utf-8')
        self.assertIn('> 원문 보존\n> 두 번째 줄', source)
        self.assertIn('%23', source)
        self.assertIn('SHA-256 `abc`', source)
        self.assertIn('처리구분: 진행', source)
        self.assertNotIn('status: closed', source)

    def test_refresh_preserves_manual_content_and_is_idempotent(self):
        renderer.render(self.output, self.config, self.data)
        path = self.output / '원문노트/사업진행-2695-89136.md'
        path.write_text(path.read_text(encoding='utf-8') + '\n## 담당자 메모\n검토 필요\n', encoding='utf-8')
        before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.output.rglob('*.md')}
        same = renderer.render(self.output, self.config, self.data)
        self.assertEqual(same['unchanged'], 17)
        self.assertEqual(before, {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.output.rglob('*.md')})
        self.data['posts'][0]['body_text'] = '수정 원문'
        renderer.render(self.output, self.config, self.data)
        text = path.read_text(encoding='utf-8')
        self.assertIn('수정 원문', text)
        self.assertTrue(text.endswith('\n## 담당자 메모\n검토 필요\n'))

    def test_unmanaged_collision_blocks_all_writes(self):
        path = self.output / '_사업 진행 종합.md'
        path.write_text('사용자 메모', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Refusing unmanaged'):
            renderer.render(self.output, self.config, self.data)
        self.assertEqual(list(self.output.rglob('*.md')), [path])
        self.assertEqual(path.read_text(encoding='utf-8'), '사용자 메모')

    def test_path_escape_blocks_all_writes(self):
        self.data['posts'][0]['attachments'][0]['path'] = '../private.txt'
        with self.assertRaisesRegex(ValueError, 'escapes output'):
            renderer.render(self.output, self.config, self.data)
        self.assertFalse(list(self.output.rglob('*.md')))

    def test_override_common_and_unknown_keep_original_dataset(self):
        self.config['overrides']['2695-89136'] = {'sites': [], 'category': '공통'}
        renderer.render(self.output, self.config, self.data)
        dashboard = (self.output / '_사업 진행 종합.md').read_text(encoding='utf-8')
        self.assertIn('공통 1건 · 미분류 0건', dashboard)
        self.assertEqual(self.data['posts'][0]['sites'], ['사이트0', '사이트1'])

    def test_invalid_sites_and_ids_rejected(self):
        self.config['sites'][0]['name'] = '../escape'
        with self.assertRaisesRegex(ValueError, 'Unsafe site'):
            renderer.render(self.output, self.config, self.data)
        self.config['sites'][0]['name'] = '사이트0'
        self.data['posts'].append(dict(self.data['posts'][0]))
        with self.assertRaisesRegex(ValueError, 'unique'):
            renderer.render(self.output, self.config, self.data)

    def test_dotted_comment_date_does_not_sort_before_newer_post(self):
        old = self.data['posts'][0]
        old['comments'][0]['date'] = '2026.09.30'
        newer = dict(old, id='2695-90000', created_at='2026-10-12 12:00:00', comments=[])
        self.assertEqual(renderer.ordered([old, newer])[0]['id'], '2695-90000')

    def test_supplemental_scope_is_separate_from_unclassified(self):
        self.config['overrides']['2695-89136'] = {'sites': [], 'category': '추가 범위'}
        renderer.render(self.output, self.config, self.data)
        text = (self.output / '_공통 및 미분류 사업 진행.md').read_text(encoding='utf-8')
        self.assertIn('추가 범위 · 시설물 예약', text)
        self.assertIn('공통 0건 · 미분류 0건 · 추가 범위 1건', text)

    def test_site_explicit_comment_does_not_leak_to_other_site_view(self):
        self.data['posts'][0]['comments'][0]['text'] = '사이트1 자료 제출 요청'
        renderer.render(self.output, self.config, self.data)
        other = (self.output / '사이트별/사이트0/_사이트0 사업 진행.md').read_text(encoding='utf-8')
        target = (self.output / '사이트별/사이트1/_사이트1 사업 진행.md').read_text(encoding='utf-8')
        self.assertNotIn('사이트1 자료 제출 요청', other)
        self.assertIn('사이트1 자료 제출 요청', target)
        aggregate = (self.output / '_사업 진행 종합.md').read_text(encoding='utf-8')
        self.assertIn('사이트1 자료 제출 요청', aggregate)

    def test_override_evidence_replaces_stale_automatic_evidence(self):
        self.data['posts'][0]['classification_evidence'] = [{'site': '사이트0', 'field': 'body', 'alias': '사이트0'}]
        self.config['overrides']['2695-89136'] = {'sites': [], 'category': '공통', 'evidence': 'Shared project template'}
        renderer.render(self.output, self.config, self.data)
        text = (self.output / '원문노트/사업진행-2695-89136.md').read_text(encoding='utf-8')
        self.assertNotIn('사이트0 · body · 명칭: 사이트0', text)
        self.assertIn('override', text)
        self.assertIn('Shared project template', text)


if __name__ == '__main__':
    unittest.main()
