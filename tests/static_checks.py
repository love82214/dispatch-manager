"""Check source syntax, HTML structure, local-only policy and release metadata."""
import argparse
import json
import re
import subprocess

import html5lib
import tinycss2

from scripts.release import CSP, ROOT, check, require, runtime_files


def stylesheet_errors(nodes):
    for node in nodes:
        if node.type == 'error':
            yield f'line {node.source_line}: {node.message}'
        elif node.type in ('at-rule', 'qualified-rule') and node.content is not None:
            yield from stylesheet_errors(tinycss2.parse_blocks_contents(node.content))


def asset_path(value):
    return value.removeprefix('./')


def run(base):
    info = check(base)
    files = set(runtime_files((ROOT / 'sw.js').read_text(encoding='utf-8')))
    for name in sorted(files):
        path = ROOT / name
        if path.suffix in ('.js', '.mjs'):
            subprocess.run(['node', '--check', str(path)], check=True)
        if path.suffix == '.css':
            syntax = tinycss2.parse_stylesheet(path.read_text(encoding='utf-8'))
            require(not (errors := list(stylesheet_errors(syntax))), f'{name}: {errors}')
            require(not any(node.type == 'at-rule' and node.lower_at_keyword == 'import' for node in syntax),
                    'CSS cannot import an external stylesheet')

    page = html5lib.HTMLParser(strict=True, namespaceHTMLElements=False).parse(
        (ROOT / 'index.html').read_text(encoding='utf-8'))
    ids = [node.attrib['id'] for node in page.iter() if 'id' in node.attrib]
    require(len(ids) == len(set(ids)), 'Duplicate HTML id')
    csp = [node.get('content') for node in page.iter('meta')
           if node.get('http-equiv', '').lower() == 'content-security-policy']
    require(csp == [CSP], 'CSP was removed or changed')
    for node in page.iter('script'):
        require(not (node.text or '').strip() and asset_path(node.get('src', '')) in files,
                'Inline or non-precached script')
    for link in page.iter('link'):
        if link.get('rel') in ('stylesheet', 'manifest', 'apple-touch-icon'):
            require(asset_path(link.get('href', '')) in files, 'A linked app asset is not precached')
    for path in page.iter('label'):
        require(path.get('for') is None or path.get('for') in ids, 'A label targets a missing HTML id')
    for node in page.iter():
        require(not any(attr.startswith('on') for attr in node.attrib), 'Inline event handler')
        if style := node.get('style'):
            require(not list(stylesheet_errors(tinycss2.parse_blocks_contents(style))),
                    'Invalid inline CSS declaration')
    manifest = json.loads((ROOT / 'manifest.webmanifest').read_text(encoding='utf-8'))
    require(manifest['start_url'] == './' and manifest['scope'] == './', 'PWA path or scope changed')
    for icon in manifest['icons']:
        require(asset_path(icon['src']) in files, 'An icon is not available offline')
    app = (ROOT / 'app.js').read_text(encoding='utf-8')
    require(set(re.findall(r"\$\(['\"]([^'\"]+)['\"]\)", app)) <= set(ids),
            'JavaScript references a missing HTML id')
    require("const KEY='dispatch-mobile-v5-local'" in app, 'The existing localStorage key changed')
    require('const raw=``;' in app, 'The default roster must be empty')
    print(f"V{info['version']}: JavaScript, HTML, CSS, CSP, manifest, offline assets and version checks passed")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', help='Git ref for the previous production app')
    run(parser.parse_args().base)
