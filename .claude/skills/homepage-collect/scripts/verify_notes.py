"""Verify generated source coverage, local links and shared vault note rules."""
import argparse
import json
from pathlib import Path
import re
import sys
import unicodedata
from urllib.parse import unquote, urlsplit

from render_notes import BEGIN, END


def verify(output, vault):
    sys.path.insert(0, str(vault / '.claude' / 'lib'))
    import note_rules
    import validate_tag
    data = json.loads((output / '원본데이터' / 'dataset.json').read_text(encoding='utf-8'))
    notes = list(output.rglob('*.md'))
    names = {}
    errors = []
    for path in notes:
        names.setdefault(unicodedata.normalize('NFC', path.stem), []).append(path)
    for post in data['posts']:
        if not (output / '원문노트' / f'사업진행-{post["id"]}.md').is_file():
            errors.append('Missing source note: ' + post['id'])
    for path in notes:
        text = path.read_text(encoding='utf-8')
        if BEGIN not in text:
            continue  # Unmanaged user notes are outside this collector's contract.
        errors.extend(f'{path.name}: {error}' for error in note_rules.check(str(path.resolve()), text, skip=()))
        # Only links the collector wrote must resolve here; manual text around the markers
        # may point anywhere in the vault.
        managed = text.split(BEGIN, 1)[1].split(END, 1)[0]
        for link in re.findall(r'\[\[([^\]]+)\]\]', managed):
            target = link.split('|', 1)[0].split('#', 1)[0]
            if len(names.get(unicodedata.normalize('NFC', target), [])) != 1:
                errors.append(f'Unresolved/ambiguous note link in {path.name}: {target}')
        for link in re.findall(r'(?<!\\)\]\(([^\n]+?)\)', managed):
            if urlsplit(link).scheme or link.startswith('#'):
                continue
            target = (path.parent / unquote(link)).resolve()
            if not target.is_relative_to(output.resolve()) or not target.is_file():
                errors.append('Invalid local file link in ' + path.name)
    if not validate_tag.validate('#업무/홈페이지').valid:
        errors.append('Generated homepage tag is invalid')
    if errors:
        raise ValueError('\n'.join(errors))
    result = {'notes': len(notes), 'source_notes': len(data['posts']), 'note_rules_and_links': 'PASS'}
    print(json.dumps(result, ensure_ascii=False))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--vault', type=Path, required=True)
    args = parser.parse_args()
    verify(args.output, args.vault)
