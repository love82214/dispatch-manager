"""Prepare and check the version of the static PWA."""
import argparse
import ast
import html
import json
import re
import subprocess
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = 'https://github.com/love82214/dispatch-manager'
VERSION_PATTERN = r'(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)(?:\.(?:0|[1-9]\d*))?'
CACHE = re.compile(r"""(?m)^const CACHE=['"]dispatch-static-v(?P<version>[^'"]+)['"];""")
ASSETS = re.compile(r'(?m)^const ASSETS=(\[[^\n]+\]);')
HTML_LABELS = (
    r'(?<=<title>每日派車管理 )V' + VERSION_PATTERN,
    r'(?<=<span class="edition">個人版 <strong>)V' + VERSION_PATTERN,
    r'(?<=<h2>程式更新</h2><strong>)V' + VERSION_PATTERN,
    r'(?<=<p id="versionStatus" class="notice" aria-live="polite">)V' + VERSION_PATTERN,
)
JS_LABEL = re.compile(r'\bV' + VERSION_PATTERN + r'(?=｜)')
UI_LOG = '<details class="changelog"><summary>版本更新紀錄</summary>'
LOG_FIELDS = ('新增', '修正', '根因', '影響範圍', '測試', '提交', '尚未實機驗證')
CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "connect-src 'none'; img-src 'self' data:; worker-src 'self'; "
    "object-src 'none'; base-uri 'none'; form-action 'none'"
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def git(*args, root=ROOT):
    return subprocess.check_output(['git', *args], cwd=root)


def version_number(value):
    require(isinstance(value, str) and re.fullmatch(VERSION_PATTERN, value),
            f'Invalid release version: {value!r}')
    parts = tuple(int(part) for part in value.split('.'))
    return (parts + (0,))[:3]


def release_info(root=ROOT):
    data = json.loads((root / 'VERSION.json').read_text(encoding='utf-8'))
    require(version_number(data['previousVersion']) < version_number(data['version']),
            'previousVersion must be older than version')
    require(date.fromisoformat(data['releaseDate']).isoformat() == data['releaseDate'],
            'releaseDate must be YYYY-MM-DD')
    return data


def cache_version(worker):
    match = CACHE.search(worker)
    require(match and len(CACHE.findall(worker)) == 1, 'Expected one dispatch-static cache declaration')
    version_number(match['version'])
    return match['version']


def runtime_files(worker):
    """Public files that travel with the app and therefore require a cache bump."""
    match = ASSETS.search(worker)
    require(match, 'Missing Service Worker precache list')
    assets = ast.literal_eval(match[1])
    require(isinstance(assets, list) and assets and all(isinstance(asset, str) and re.fullmatch(
        r'\./[\w.-]+(?:/[\w.-]+)*', asset) and not {'..', '.'}.intersection(asset[2:].split('/'))
        for asset in assets), 'Precache must contain local relative paths')
    files = {asset[2:] for asset in assets}
    require(len(files) == len(assets), 'Duplicate precache entry')
    require({'index.html', 'app.js', 'manifest.webmanifest'} <= files,
            'Required application file is missing from precache')
    return sorted(files | {'sw.js'})


def check_labels(source, app, version):
    for pattern in HTML_LABELS:
        require(re.findall(pattern, source) == [f'V{version}'], 'Homepage or settings version is out of date')
    labels = JS_LABEL.findall(app)
    require(labels and set(labels) == {f'V{version}'}, 'JavaScript version notices are out of date')
    require(f'{UI_LOG}<p><strong>V{version}</strong>' in source,
            'The in-app update notes must start with the current version')


def check_log(log, info):
    header = f"## V{info['version']} · {info['releaseDate']}"
    match = re.search(rf'^{re.escape(header)}\n(.*?)(?=^## |\Z)', log, re.M | re.S)
    require(match, f'CHANGELOG.md needs {header}')
    for label in LOG_FIELDS:
        require(re.search(rf'^- \*\*{label}\*\*[ \t]+\S[^\n]*$', match[1], re.M),
                f'CHANGELOG.md entry is missing {label}')


def upgrade_ref(info, base=None, root=ROOT):
    previous = info['previousVersion']
    if base and base.strip('0') and cache_version(git('show', f'{base}:sw.js', root=root).decode()) == previous:
        # Also supports an emergency fix when Pages deployed the base but its audit failed.
        return base
    tag = f'v{previous}'
    require(cache_version(git('show', f'{tag}:sw.js', root=root).decode()) == previous,
            'Previous release tag does not match its Service Worker')
    return tag


def check(base=None, root=ROOT):
    info = release_info(root)
    version = info['version']
    worker = (root / 'sw.js').read_text(encoding='utf-8')
    files = runtime_files(worker)
    require(cache_version(worker) == version, 'Service Worker cache differs from VERSION.json')
    require(all((root / name).is_file() for name in files), 'A precached file is missing')
    check_labels((root / 'index.html').read_text(encoding='utf-8'),
                 (root / 'app.js').read_text(encoding='utf-8'), version)
    check_log((root / 'CHANGELOG.md').read_text(encoding='utf-8'), info)
    upgrade_ref(info, base, root)
    if base:
        base_worker = git('show', f'{base}:sw.js', root=root).decode()
        base_version = cache_version(base_worker)
        changed = git('diff', '--name-only', base, '--',
                      *sorted(set(files) | set(runtime_files(base_worker))), root=root).strip()
        if changed or version != base_version:
            require(version_number(version) > version_number(base_version),
                    'Application changes require a newer version and a new cache')
            require(info['previousVersion'] == base_version,
                    'Upgrade tests must start at the version in the destination branch')
        else:
            version_exists = subprocess.run(
                ['git', 'cat-file', '-e', f'{base}:VERSION.json'], cwd=root,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False
            ).returncode == 0
            if version_exists:
                require((root / 'VERSION.json').read_bytes() == git('show', f'{base}:VERSION.json', root=root),
                        'Keep recorded release metadata unchanged on maintenance-only updates')
    return info


def today_in_taipei():
    return datetime.now(ZoneInfo('Asia/Taipei')).date().isoformat()


def prepare(args, root=ROOT):
    info = release_info(root)
    current = info['version']
    version = args.version
    require(version_number(version) > version_number(current), 'Use a version newer than the current release')
    require(date.fromisoformat(args.date).isoformat() == args.date, 'Use YYYY-MM-DD for the release date')
    index = (root / 'index.html').read_text(encoding='utf-8')
    app = (root / 'app.js').read_text(encoding='utf-8')
    worker = (root / 'sw.js').read_text(encoding='utf-8')
    check_labels(index, app, current)
    require(cache_version(worker) == current, 'Prepare from a consistent version baseline')
    for pattern in HTML_LABELS:
        index = re.sub(pattern, f'V{version}', index)
    index = index.replace(UI_LOG, f'{UI_LOG}<p><strong>V{version}</strong> {html.escape(args.summary)}</p>', 1)
    app = JS_LABEL.sub(f'V{version}', app)
    worker = worker.replace(f'dispatch-static-v{current}', f'dispatch-static-v{version}', 1)
    new_info = {'version': version, 'previousVersion': current, 'releaseDate': args.date}
    items = (
        args.summary, args.fixes, args.cause, args.impact, args.tests,
        f'[v{version}]({REPOSITORY}/tree/v{version})', args.unverified,
    )
    require(all(item.strip() and not set(item).intersection('\r\n') for item in items),
            'Provide a nonempty single line for every changelog field')
    log = (root / 'CHANGELOG.md').read_text(encoding='utf-8')
    first = log.index('\n## ')
    entry = f'\n## V{version} · {args.date}\n\n'
    entry += '\n'.join(f'- **{label}** {item}' for label, item in zip(LOG_FIELDS, items))
    log = log[:first] + entry + '\n' + log[first:]
    check_labels(index, app, version)
    check_log(log, new_info)
    for name, content in (
        ('index.html', index), ('app.js', app), ('sw.js', worker),
        ('CHANGELOG.md', log), ('VERSION.json', json.dumps(new_info, ensure_ascii=False, indent=2) + '\n')
    ):
        (root / name).write_text(content, encoding='utf-8')
    return new_info


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    validator = commands.add_parser('check', help='check version labels, cache, changelog and upgrade baseline')
    validator.add_argument('--base', help='Git ref of the destination branch before this change')
    release = commands.add_parser('prepare', help='update all version labels and add a changelog entry')
    release.add_argument('version')
    release.add_argument('--date', default=today_in_taipei())
    for flag in ('summary', 'fixes', 'cause', 'impact', 'tests', 'unverified'):
        release.add_argument(f'--{flag}', required=True)
    args = parser.parse_args()
    try:
        info = prepare(args) if args.command == 'prepare' else check(args.base)
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'{error}\n')
    print(f"V{info['version']} / dispatch-static-v{info['version']} · {info['releaseDate']}")


if __name__ == '__main__':
    main()
