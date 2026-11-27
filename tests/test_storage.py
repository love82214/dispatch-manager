"""Exercise read-only recovery, write failures and concurrent use of one origin."""
import json
import unittest

from playwright.sync_api import expect

from tests.browser_support import (
    FIXTURE, FIXTURE_TEXT, KEY, VIEWS, BrowserCase, get_download, navigate, persisted,
    restore, stored_text, wait_for, warn,
)

DENY_WRITES = """
window.rejectWrites = true;
const put = Storage.prototype.setItem;
Storage.prototype.setItem = function(k, v) {
  if (k === key && window.rejectWrites) throw new DOMException('Synthetic limit', 'QuotaExceededError');
  return put.call(this, k, v);
};
"""
DENY_READS = """
window.normalGet = Storage.prototype.getItem;
Storage.prototype.getItem = function(k) {
  if (k === key) throw new DOMException('Synthetic denial', 'SecurityError');
  return normalGet.call(this, k);
};
"""


class StorageSafety(BrowserCase):
    def test_corrupt_bytes_and_invalid_schema_remain_recoverable(self):
        malformed = '{ "rows": ['
        cases = (malformed, '', json.dumps(dict(FIXTURE, rows=[None])))
        for seed in cases:
            with self.subTest(seed=seed), self.app(seed=seed, init=DENY_WRITES) as (page, _):
                for view in VIEWS:
                    navigate(page, view)
                    warn(page, '安全復原模式')
                page.locator('#nextDate').click()
                navigate(page, 'overview')
                page.locator('[data-quick="new"]').click()
                expect(page.locator('#editor')).to_be_hidden()
                self.assertEqual(stored_text(page), seed)
                page.reload()
                _, raw_backup = get_download(page, '#downloadRaw')
                self.assertEqual(raw_backup, seed.encode())
                restore(page, b'{}')
                expect(page.locator('#toast')).to_contain_text('備份格式不符')
                restore(page, FIXTURE_TEXT.encode(), accept=False)
                self.assertEqual(stored_text(page), seed)
                restore(page, FIXTURE_TEXT.encode(), accept=True)
                warn(page, '備份還原未能儲存')
                self.assertEqual(stored_text(page), seed)
                page.evaluate('window.rejectWrites = false')
                restore(page, FIXTURE_TEXT.encode(), accept=True)
                expect(page.locator('#toast')).to_have_text('已還原備份')
                expect(page.locator('#storageBanner')).to_be_hidden()
                self.assertEqual(persisted(page), FIXTURE)

    def test_storage_read_denied_does_not_erase_records(self):
        with self.app(seed=FIXTURE_TEXT, init=DENY_READS) as (page, _):
            warn(page, '無法讀取')
            page.locator('#prevDate').click()
            navigate(page, 'settings')
            restore(page, FIXTURE_TEXT.encode())
            self.assertEqual(page.evaluate('(key) => normalGet.call(localStorage, key)', KEY), FIXTURE_TEXT)

    def test_quota_failure_is_persistent_and_editor_can_retry(self):
        with self.app(seed=FIXTURE_TEXT, init=DENY_WRITES) as (page, _):
            navigate(page, 'dispatch')
            page.locator('[data-check]').click()
            warn(page, '本機儲存失敗')
            expect(page.locator('[data-check]')).to_be_checked()
            page.locator('[data-edit]').click()
            page.locator('#eDriver').fill('虛構儲存重試')
            page.locator('#editForm footer button').click()
            expect(page.locator('#editorStorage')).to_contain_text('本次異動未儲存')
            expect(page.locator('#editor')).to_be_visible()
            expect(page.locator('#eDriver')).to_have_value('虛構儲存重試')
            expect(page.locator('#toast')).not_to_have_text('已儲存異動')
            self.assertEqual(stored_text(page), FIXTURE_TEXT)
            page.locator('#closeEditor').click()
            for view in VIEWS:
                navigate(page, view)
                warn(page, '本機儲存失敗')
            navigate(page, 'dispatch')
            page.locator('[data-edit]').click()
            page.locator('#eDriver').fill('虛構儲存重試')
            page.evaluate('window.rejectWrites = false')
            page.locator('#editForm footer button').click()
            expect(page.locator('#toast')).to_have_text('已儲存異動')
            expect(page.locator('#storageBanner')).to_be_hidden()
            self.assertEqual(persisted(page)['rows'][0]['driver'], '虛構儲存重試')

    def test_two_queued_writes_do_not_overwrite_each_other(self):
        with self.app(seed=FIXTURE_TEXT) as (first, context):
            second = context.new_page()
            second.goto(self.server.url)
            for page, name in ((first, '虛構分頁甲'), (second, '虛構分頁乙')):
                navigate(page, 'dispatch')
                page.locator('[data-edit]').click()
                page.locator('#eDriver').fill(name)

            first.evaluate("""key => {
              navigator.locks.request(key, () => new Promise(resolve => { window.releaseTest = resolve; }));
            }""", KEY)
            first.wait_for_function('() => typeof window.releaseTest === "function"')
            def queued_writes():
                return first.evaluate("""async key => (await navigator.locks.query()).pending
                    .filter(lock => lock.name === key).length""", KEY)

            try:
                first.locator('#editForm footer button').click()
                wait_for(lambda: queued_writes() == 1, 'First write did not acquire a place in the queue')
                second.locator('#editForm footer button').click()
                wait_for(lambda: queued_writes() == 2, 'Second write did not join the queue')
            finally:
                first.evaluate('window.releaseTest()')
            expect(first.locator('#toast')).to_have_text('已儲存異動')
            expect(second.locator('#editorStorage')).to_contain_text('另一個分頁已變更')
            expect(second.locator('#eDriver')).to_have_value('虛構分頁乙')
            self.assertEqual(persisted(second)['rows'][0]['driver'], '虛構分頁甲')
            second.locator('#closeEditor').click()
            warn(second, '本頁已停止寫入')
            second.locator('#nextDate').click()
            self.assertEqual(persisted(second), persisted(first))
            second.locator('#reloadStorage').click()
            navigate(second, 'dispatch')
            expect(second.locator('#storageBanner')).to_be_hidden()
            expect(second.locator('#list')).to_contain_text('虛構分頁甲')

    def test_unsupported_web_locks_is_read_only(self):
        no_locks = "Object.defineProperty(Navigator.prototype, 'locks', {get: () => undefined});"
        with self.app(seed=FIXTURE_TEXT, init=no_locks) as (page, _):
            warn(page, '無法安全處理多分頁寫入')
            navigate(page, 'dispatch')
            expect(page.locator('#list')).to_contain_text('虛構車長')
            page.locator('[data-edit]').click()
            expect(page.locator('#editor')).to_be_hidden()
            page.locator('#nextDate').click()
            self.assertEqual(stored_text(page), FIXTURE_TEXT)


if __name__ == '__main__':
    unittest.main()
