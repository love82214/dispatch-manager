"""Regression checks for version generation, release gating and Pages verification."""
import shutil
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts import release, verify_pages


class ReleaseTools(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        worker = (release.ROOT / 'sw.js').read_text(encoding='utf-8')
        for name in release.runtime_files(worker) + ['VERSION.json', 'CHANGELOG.md']:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(release.ROOT / name, path)
        self.info = release.release_info(self.root)
        self.git('init', '-q')
        self.git('config', 'user.name', 'Release Test')
        self.git('config', 'user.email', 'release-test@example.invalid')
        self.git('add', '.')
        self.git('commit', '-qm', 'Fictional current release')
        self.git('tag', 'v' + self.info['version'])
        # An isolated Git tag suffices to exercise the baseline metadata check.
        sw = self.root / 'sw.js'
        sw.write_text(worker.replace(
            'dispatch-static-v' + self.info['version'],
            'dispatch-static-v' + self.info['previousVersion'], 1
        ), encoding='utf-8')
        self.git('add', 'sw.js')
        self.git('commit', '-qm', 'Fictional prior release')
        self.git('tag', 'v' + self.info['previousVersion'])
        self.git('checkout', '-q', 'v' + self.info['version'])

    def git(self, *args):
        return release.git(*args, root=self.root)

    def prepare_next(self):
        major, minor, patch_version = release.version_number(self.info['version'])
        return release.prepare(SimpleNamespace(
            version=f'{major}.{minor}.{patch_version + 1}',
            date=(date.fromisoformat(self.info['releaseDate']) + timedelta(days=1)).isoformat(),
            summary='Synthetic release', fixes='Synthetic fix', cause='Synthetic root cause',
            impact='Synthetic scope', tests='Version checks passed', unverified='Physical iPhone',
        ), self.root)

    def test_docs_can_change_without_bumping_the_app(self):
        (self.root / 'AGENTS.md').write_text('Synthetic policy', encoding='utf-8')
        self.assertEqual(release.check('HEAD', self.root), self.info)

    def test_runtime_change_requires_a_bump(self):
        with (self.root / 'app.js').open('a', encoding='utf-8') as script:
            script.write('\n// Fictional runtime change\n')
        with self.assertRaisesRegex(ValueError, 'newer version and a new cache'):
            release.check('HEAD', self.root)

    def test_prepare_updates_html_status_cache_log_and_upgrade_baseline(self):
        info = self.prepare_next()
        self.assertEqual(release.check('HEAD', self.root), info)
        self.assertEqual(info['previousVersion'], self.info['version'])

    def test_emergency_fix_uses_exact_base_when_the_previous_tag_is_missing(self):
        self.git('tag', '--delete', 'v' + self.info['version'])
        info = self.prepare_next()
        self.assertEqual(release.upgrade_ref(info, 'HEAD', self.root), 'HEAD')
        self.assertEqual(release.check('HEAD', self.root), info)

    def test_rejects_stale_browser_label_and_cache(self):
        info = self.prepare_next()
        index = self.root / 'index.html'
        sw = self.root / 'sw.js'
        fixed_html = index.read_text(encoding='utf-8')
        index.write_text(fixed_html.replace(f"V{info['version']}", 'V' + self.info['version'], 1), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'version is out of date'):
            release.check(root=self.root)
        index.write_text(fixed_html, encoding='utf-8')
        sw.write_text(sw.read_text(encoding='utf-8').replace(
            f"dispatch-static-v{info['version']}", 'dispatch-static-v' + self.info['version'], 1), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'cache differs'):
            release.check(root=self.root)

    def test_live_site_must_match_homepage_version_and_offline_assets(self):
        def read(url):
            asset = url.removeprefix(verify_pages.SITE) or 'index.html'
            return (self.root / asset).read_bytes()

        verify_pages.check_site(verify_pages.SITE, self.root, read)
        for stale_file in ('', 'VERSION.json', 'sw.js', 'app.js'):
            with self.subTest(file=stale_file):
                with self.assertRaisesRegex(ValueError, 'Published file differs'):
                    verify_pages.check_site(verify_pages.SITE, self.root,
                                            lambda url: b'old bytes' if url == verify_pages.SITE + stale_file else read(url))

    @patch.object(verify_pages, 'github_json')
    def test_deployment_record_has_to_match_release_commit(self, github_json):
        expected = {'state': 'success'}
        github_json.side_effect = [[{'sha': 'older', 'id': 1}, {'sha': 'current', 'id': 2}], [expected]]
        self.assertEqual(verify_pages.latest_deployment('example/project', 'current'), expected)
        self.assertTrue(github_json.call_args.args[0].endswith('/2/statuses?per_page=1'))


if __name__ == '__main__':
    unittest.main()
