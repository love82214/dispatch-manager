"""Verify the exact GitHub Pages deployment and retain its release tag."""
import argparse
import json
import os
import subprocess
from datetime import datetime
from time import monotonic, sleep
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from scripts.release import ROOT, git, release_info, require, runtime_files

SITE = 'https://love82214.github.io/dispatch-manager/'


def github_json(path):
    api = os.environ.get('GITHUB_API_URL', 'https://api.github.com')
    request = Request(api + path, headers={'Accept': 'application/vnd.github+json'})
    request.add_unredirected_header('Authorization', 'Bearer ' + os.environ['GH_TOKEN'])
    with urlopen(request, timeout=10) as response:
        return json.load(response)


def latest_deployment(repo, sha):
    query = urlencode({'sha': sha, 'environment': 'github-pages', 'per_page': 10})
    path = f'/repos/{repo}/deployments'
    deployments = github_json(f'{path}?{query}')
    for deployment in deployments:
        if deployment['sha'] != sha:
            continue
        statuses = github_json(f"{path}/{deployment['id']}/statuses?per_page=1")
        if statuses:
            return statuses[0]
    return None


def read_public(url):
    request = Request(url, headers={'Cache-Control': 'no-cache', 'User-Agent': 'dispatch-manager-release-check'})
    with urlopen(request, timeout=12) as response:
        require(response.status == 200 and response.url == url, f'Unexpected response for {url}')
        return response.read()


def check_site(site, root=ROOT, read=read_public):
    worker = (root / 'sw.js').read_text(encoding='utf-8')
    expected = {name: name for name in runtime_files(worker) + ['VERSION.json']}
    expected[''] = 'index.html'
    for relative, filename in expected.items():
        url = urljoin(site, relative)
        require(read(url) == (root / filename).read_bytes(),
                f'Published file differs from the release commit: {url}')


def await_deployment(repo, sha, site, timeout):
    deadline = monotonic() + timeout
    last = 'Waiting for the github-pages deployment record'
    while monotonic() < deadline:
        try:
            status = latest_deployment(repo, sha)
            if status and status['state'] in ('failure', 'error', 'inactive'):
                raise RuntimeError(f"GitHub Pages deployment ended with {status['state']}")
            if status and status['state'] == 'success':
                environment_url = status.get('environment_url')
                if environment_url:
                    require(environment_url.rstrip('/') + '/' == site,
                            'GitHub Pages deployment URL differs from the configured site')
                check_site(site)
                return status
            if status:
                last = f"GitHub Pages deployment status is {status['state']}"
        except HTTPError as error:
            if error.url.startswith(os.environ.get('GITHUB_API_URL', 'https://api.github.com') + '/') and error.code in (401, 403, 404):
                raise RuntimeError(f'Cannot read GitHub deployment records: HTTP {error.code}') from error
            last = f'HTTP {error.code} from {error.url}'
        except (URLError, TimeoutError, ValueError) as error:
            last = str(error)
        print(last, flush=True)
        sleep(12)
    raise RuntimeError(f'Production site verification incomplete: {last}')


def keep_release_tag(version, sha, evidence):
    tag = 'v' + version
    runtime = runtime_files((ROOT / 'sw.js').read_text(encoding='utf-8'))
    ref = f'refs/tags/{tag}'
    existing = git('ls-remote', '--tags', 'origin', ref).strip()
    if existing:
        git('fetch', 'origin', ref)
        git('merge-base', '--is-ancestor', f'{ref}^{{commit}}', sha)
        # Infrastructure-only commits can deploy the same app version without moving its tag.
        git('diff', '--exit-code', f'{ref}^{{commit}}', sha, '--', *runtime)
        return f'`{tag}` 保留原發布提交。'
    identity = ('-c', 'user.name=github-actions[bot]', '-c',
                'user.email=41898282+github-actions[bot]@users.noreply.github.com')
    git(*identity, 'tag', '-a', tag, sha, '-m', evidence)
    git('push', 'origin', ref)
    return f'`{tag}` → `{sha}`。'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--timeout', type=int, default=420, help='Maximum time to wait for Pages, in seconds')
    parser.add_argument('--check-site-only', action='store_true',
                        help='Compare production responses to this checkout without creating a tag')
    args = parser.parse_args()
    info = release_info()
    version = info['version']
    try:
        if args.check_site_only:
            check_site(SITE)
            print(f'Confirmed V{version} at {SITE}')
            return
        sha = os.environ['GITHUB_SHA']
        repo = os.environ['GITHUB_REPOSITORY']
        require(git('rev-parse', 'HEAD').decode().strip() == sha, 'Checkout must match the release commit')
        deployment = await_deployment(repo, sha, SITE, args.timeout)
        date = datetime.fromisoformat(deployment['created_at'].replace('Z', '+00:00'))
        published = date.astimezone(ZoneInfo('Asia/Taipei')).isoformat(timespec='seconds')
        run = f"https://github.com/{repo}/actions/runs/{os.environ['GITHUB_RUN_ID']}"
        evidence = f'V{version}: {sha}\nGitHub Pages verified at {SITE}\nPublished: {published}\nChecks: {run}'
        tag_result = keep_release_tag(version, sha, evidence)
    except (RuntimeError, OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'{error}\n')

    summary = (
        f'## 正式網站 V{version} 已驗證\n\n'
        f'- 版本與靜態資源回應和 `{sha}` 一致。\n'
        f'- 部署時間（臺灣）：{published}。\n'
        f'- 版本標籤：{tag_result}\n'
        f'- [正式網站]({SITE}) · [GitHub Actions]({run})\n'
        f'- iPhone 實機結果請參閱 CHANGELOG.md。\n'
    )
    print(summary)
    with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as log:
        log.write(summary)


if __name__ == '__main__':
    main()
