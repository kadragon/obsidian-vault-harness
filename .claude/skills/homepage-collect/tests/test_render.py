"""Offline renderer contracts: scope, quotations, refresh safety and collisions."""
import importlib.util
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

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

    def test_local_links_resolve_through_symlinked_output(self):
        from urllib.parse import unquote
        alias = self.output / 'alias'
        actual = self.output / 'actual'
        actual.mkdir()
        alias.symlink_to(actual, target_is_directory=True)
        attachment = actual / 'attachment.pdf'
        attachment.write_bytes(b'original')
        note = Path('notes/source.md')
        (alias / note).parent.mkdir()
        link = renderer.local_link('attachment.pdf', note, alias)
        target = (alias / note).parent / unquote(link.split('](', 1)[1][:-1])
        self.assertEqual(target.resolve(), attachment.resolve())
        self.assertTrue(target.is_file())

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


    def test_source_markdown_is_literal_and_attachment_labels_verify(self):
        import sys
        from urllib.parse import unquote
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
        import verify_notes
        post = self.data['posts'][0]
        post['title'] = '[[메인]] <!-- hidden -->'
        post['body_text'] = '#태그 [[메인]] [참고](첨부 확인) <!-- homepage-collect:end -->'
        post['comments'][0]['text'] = '[참고](missing) #태그 <!-- hidden'
        post['attachments'][0]['name'] = '회의록[1차](최종).hwp'
        for field in ('path',):
            target = self.output / post['attachments'][0][field]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b'abc')
        archive = self.output / post['source_html']
        archive.parent.mkdir(parents=True, exist_ok=True)
        archive.write_text('source')
        (self.output / '원본데이터').mkdir()
        import json
        (self.output / '원본데이터/dataset.json').write_text(json.dumps(self.data))
        renderer.render(self.output, self.config, self.data)
        text = (self.output / '원문노트/사업진행-2695-89136.md').read_text()
        self.assertNotIn('[[메인]]', text)
        self.assertNotIn('#태그', text)
        self.assertEqual(text.count(renderer.END), 1)
        verify_notes.verify(self.output, Path(__file__).resolve().parents[4])
        self.assertEqual(renderer.render(self.output, self.config, self.data)['unchanged'], 17)

    def test_weekly_collector_skips_generated_views_but_keeps_manual_project(self):
        import subprocess
        vault = self.output / 'vault'
        project = vault / '12_Projects'
        project.mkdir(parents=True)
        for area in ('10_Areas', '14_Changes'):
            (vault / area).mkdir()
        renderer.render(project, self.config, self.data)
        generated = list(project.rglob('*.md'))
        manual = project / 'manual.md'
        manual.write_text('---\nstatus: active\n---\nManual project')
        (vault / '14_Changes' / 'change.md').write_text('---\nstatus: open\n---')
        script = Path(__file__).resolve().parents[2] / 'weekly-report-compile/scripts/collect_active_notes.sh'
        for newline in ('\n', '\r\n'):
            with self.subTest(newline=repr(newline)):
                for note in generated:
                    note.write_bytes(note.read_text(encoding='utf-8').replace('\n', newline).encode('utf-8'))
                result = subprocess.run(['bash', str(script), str(vault)], capture_output=True, text=True, check=True)
                paths = set(result.stdout.splitlines())
                self.assertIn(str(manual), paths)
                self.assertTrue(all(str(note) not in paths for note in generated))


if __name__ == '__main__':
    unittest.main()
