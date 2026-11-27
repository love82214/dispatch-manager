"""Run with python -m unittest tests.test_browser -v in Chromium or Playwright WebKit."""
import json
import os
import tempfile
import unittest
from pathlib import Path

from playwright.sync_api import expect

from scripts.release import ROOT, git, release_info, runtime_files, upgrade_ref
from tests.browser_support import (
    ENGINE, FIXTURE, FIXTURE_TEXT, NOW, PREVIOUS, ROSTER, TODAY, TOMORROW,
    VERSION, VIEWS, YESTERDAY, BrowserCase, assert_stats, get_download, navigate,
    persisted, restore, stored_text, wait_cache, wait_for,
)


class BrowserRegression(BrowserCase):
    def test_responsive_layout_and_iphone_apis(self):
        for width in (320, 375, 390, 430, 768, 1440):
            with self.subTest(width=width), self.app(width=width, seed=FIXTURE_TEXT) as (page, context):
                expect(page).to_have_title(f'每日派車管理 V{VERSION}')
                self.assertTrue(page.evaluate("""() => isSecureContext &&
                  typeof navigator.locks?.request === 'function' && !!navigator.serviceWorker &&
                  !!window.visualViewport && typeof HTMLDialogElement.prototype.showModal === 'function' &&
                  CSS.supports('padding-bottom', 'env(safe-area-inset-bottom)')"""))
                if ENGINE == 'chromium' and width == 390:
                    context.new_cdp_session(page).send('Emulation.setSafeAreaInsetsOverride', {
                        'insets': {'top': 47, 'bottom': 34, 'left': 0, 'right': 0}
                    })
                    expect(page.locator('.bottom-nav')).to_have_css('padding-bottom', '40.4px')
                    expect(page.locator('main')).to_have_css('padding-top', '47px')
                expect(page.locator('.bottom-nav')).to_have_css('position', 'fixed')
                navigate(page, 'settings')
                expect(page.locator('#checkVersion')).to_be_visible()
                self.assertTrue(page.locator('#checkVersion').evaluate("""button => {
                  const style = getComputedStyle(button);
                  return style.color !== style.backgroundColor;
                }"""))
                original = stored_text(page)
                page.locator('#theme').select_option('dark')
                page.locator('#fontSize').select_option('large')
                expect(page.locator('html')).to_have_css('color-scheme', 'dark')
                expect(page.locator('html')).to_have_css('font-size', '19px')
                for view in VIEWS:
                    navigate(page, view)
                    self.assertTrue(page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'))
                page.locator('#theme').select_option('light')
                expect(page.locator('html')).to_have_css('color-scheme', 'light')
                page.locator('#theme').select_option('system')
                page.emulate_media(color_scheme='dark')
                expect(page.locator('html')).to_have_css('color-scheme', 'dark')
                self.assertEqual(stored_text(page), original)
                page.reload()
                expect(page.locator('html')).to_have_css('font-size', '19px')
                navigate(page, 'dispatch')
                page.locator('[data-edit]').click()
                page.set_viewport_size({'width': width, 'height': 390})
                page.locator('#eTask').focus()
                expect(page.locator('#closeEditor')).to_be_in_viewport()
                expect(page.locator('#editForm footer button')).to_be_in_viewport()
                page.locator('#closeEditor').click()
                self.assertEqual(stored_text(page), original)

    def test_roster_dispatch_and_stats(self):
        with self.app() as (page, _):
            page.locator('[data-quick="import"]').click()
            page.locator('#source').fill(ROSTER)
            page.locator('#importMode').select_option('replace')
            page.locator('#parse').click()
            expect(page.locator('#parseResult')).to_contain_text('辨識 5 輛')
            page.once('dialog', lambda dialog: dialog.accept())
            page.locator('#apply').click()
            expect(page.locator('[data-check="軍1-00000"]')).to_be_checked()
            page.locator('[data-group="虛構甲組"] summary').click()
            page.locator('#search').fill('虛構')
            expect(page.locator('[data-group="虛構甲組"]')).not_to_have_attribute('open', '')
            navigate(page, 'overview')
            expect(page.locator('#completionValue')).to_have_text('50%')
            _, exported = get_download(page, '[data-quick="export"]')
            self.assertIn('虛構備註', exported.decode('utf-8-sig'))
            page.locator('[data-unit="虛構甲組"]').click()
            expect(page.locator('#unit')).to_have_value('虛構甲組')
            expect(page.locator('[data-group="虛構乙組"]')).to_have_count(0)
            page.locator('[data-filter="pending"]').click()
            expect(page.locator('[data-check]')).to_have_count(1)
            page.locator('[data-check]').click()
            expect(page.locator('[data-check]')).to_have_count(0)
            page.locator('[data-filter="all"]').click()
            page.locator('[data-edit="軍2-00000"]').click()
            page.locator('#eDriver').fill('虛構新駕駛')
            page.locator('#eTaskChoice').select_option('custom')
            page.locator('#eTaskCustom').fill('虛構自訂任務')
            page.locator('#eTask').fill('虛構新備註')
            page.locator('#eFixed').check()
            page.locator('#editForm footer button').click()
            expect(page.locator('#editor')).to_be_hidden()
            expect(page.locator('[data-check="軍2-00000"]')).not_to_be_checked()
            self.assertEqual(next(row for row in persisted(page)['base'] if row['id'] == '軍2-00000')['task'],
                             '虛構自訂任務')
            expect(page.locator('#list')).to_contain_text('虛構新備註')
            navigate(page, 'statistics')
            for mode, total in [('all', 5), ('normal', 2), ('done', 1), ('pending', 1), ('other', 1)]:
                with self.subTest(mode=mode):
                    page.locator('#statMode').select_option(mode)
                    assert_stats(page, total)
            navigate(page, 'dispatch')
            page.locator('#newCar').click()
            page.locator('#eId').fill('軍T-00001')
            page.locator('#eCaptain').fill('虛構新增車長')
            page.locator('#eDriver').fill('虛構新增駕駛')
            page.locator('#editForm footer button').click()
            expect(page.locator('[data-check="軍T-00001"]')).to_have_count(1)
            page.locator('[data-edit="軍T-00001"]').click()
            page.once('dialog', lambda dialog: dialog.dismiss())
            page.locator('#deleteCar').click()
            expect(page.locator('#editor')).to_be_visible()
            page.once('dialog', lambda dialog: dialog.accept())
            page.locator('#deleteCar').click()
            expect(page.locator('[data-check="軍T-00001"]')).to_have_count(0)

    def test_date_history_reset_and_legacy_backup(self):
        with self.app(seed=FIXTURE_TEXT) as (page, _):
            page.locator('#prevDate').click()
            expect(page.locator('#workDate')).to_have_value(YESTERDAY)
            self.assertEqual(persisted(page)['rows'], FIXTURE['history'][YESTERDAY])
            page.reload()
            expect(page.locator('#workDate')).to_have_value(YESTERDAY)
            navigate(page, 'records')
            page.locator(f'[data-preview-date="{TODAY}"]').click()
            expect(page.locator('#historyText')).to_contain_text('虛構今日備註')
            page.locator(f'[data-date="{TODAY}"]').click()
            expect(page.locator('#workDate')).to_have_value(TODAY)
            page.locator('#nextDate').click()
            expect(page.locator('#workDate')).to_have_value(TOMORROW)
            expect(page.locator('#dateHint')).to_have_text('未來日期')
            page.locator('#workDate').fill('2020-01-15')
            expect(page.locator('#dateHint')).to_have_text('過去日期')
            page.locator('#goToday').click()
            expect(page.locator('#workDate')).to_have_value(TODAY)
            navigate(page, 'settings')
            page.once('dialog', lambda dialog: dialog.dismiss())
            page.locator('#reset').click()
            self.assertEqual(persisted(page)['rows'], FIXTURE['rows'])
            page.once('dialog', lambda dialog: dialog.accept())
            page.locator('#reset').click()
            wait_for(lambda: persisted(page)['rows'] == FIXTURE['base'], 'Reset did not change the active date')
            legacy = json.loads(FIXTURE_TEXT)
            for row in legacy['rows'] + legacy['base'] + legacy['history'][YESTERDAY]:
                del row['task']
            restore(page, json.dumps(legacy).encode(), accept=False)
            self.assertEqual(persisted(page)['rows'], FIXTURE['base'])
            restore(page, json.dumps(legacy).encode(), accept=True)
            expect(page.locator('#toast')).to_have_text('已還原備份')
            self.assertEqual(persisted(page)['rows'][0]['task'], '')
            self.assertEqual(persisted(page)['history'][YESTERDAY][0]['checked'], True)
            _, exported = get_download(page, '#backup')
            self.assertEqual(json.loads(exported), persisted(page))

    def test_taiwan_midnight_does_not_erase_previous_dates(self):
        midnight = NOW.replace(hour=23, minute=59, second=57)
        with self.app(seed=FIXTURE_TEXT, time=midnight, ticking=True) as (page, _):
            page.clock.fast_forward(5000)
            expect(page.locator('#workDate')).to_have_value(TOMORROW)
            self.assertEqual(persisted(page)['history'][TODAY], FIXTURE['rows'])
            for date in FIXTURE['history']:
                self.assertEqual(persisted(page)['history'][date], FIXTURE['history'][date])

    def test_old_version_auto_update_and_offline(self):
        previous_ref = upgrade_ref(release_info(), os.environ.get('UPGRADE_BASE_REF') or None)
        worker = git('show', f'{previous_ref}:sw.js').decode()
        with tempfile.TemporaryDirectory() as folder:
            previous = Path(folder)
            for name in runtime_files(worker):
                entry = previous / name
                entry.parent.mkdir(parents=True, exist_ok=True)
                entry.write_bytes(git('show', f'{previous_ref}:{name}'))
            with self.app(seed=FIXTURE_TEXT, previous=previous) as (page, context):
                expect(page).to_have_title(f'每日派車管理 V{PREVIOUS}')
                wait_cache(page, PREVIOUS)
                page.reload()
                page.wait_for_function('() => typeof reg !== "undefined" && reg !== null')
                if page.locator('.bottom-nav').count():
                    navigate(page, 'settings')
                baseline = stored_text(page)
                backup = get_download(page, '#backup')
                if page.locator('.bottom-nav').count():
                    navigate(page, 'dispatch')
                page.locator('[data-edit]').click()
                self.server.directory = ROOT

                def focus_detected_update():
                    page.evaluate("window.dispatchEvent(new Event('focus'))")
                    return '新版本已下載' in page.locator('#versionStatus').inner_text()

                wait_for(focus_detected_update, 'Focus did not discover the newer waiting worker')
                expect(page).to_have_title(f'每日派車管理 V{PREVIOUS}')
                expect(page.locator('#editor')).to_be_visible()
                page.locator('#closeEditor').click()
                expect(page).to_have_title(f'每日派車管理 V{VERSION}', timeout=15000)
                wait_cache(page, VERSION)
                self.assertEqual(stored_text(page), baseline)
                navigate(page, 'settings')
                self.assertEqual(get_download(page, '#backup'), backup)
                page.locator('#checkVersion').click()
                expect(page.locator('#versionStatus')).to_contain_text('已檢查更新')
                # Disconnect the origin itself so the cached navigation is tested in both engines.
                self.server.reachable = False
                page.close()
                page = context.new_page()
                page.goto(self.server.url)
                expect(page).to_have_title(f'每日派車管理 V{VERSION}')
                expect(page.locator('.bottom-nav')).to_have_css('position', 'fixed')
                wait_cache(page, VERSION)
                self.assertEqual(stored_text(page), baseline)
                navigate(page, 'dispatch')
                page.locator('[data-check]').click()
                expect(page.locator('[data-check]')).not_to_be_checked()
                wait_for(lambda: not persisted(page)['rows'][0]['checked'], 'Offline change was not saved')
                page.reload()
                navigate(page, 'dispatch')
                expect(page.locator('[data-check]')).not_to_be_checked()


if __name__ == '__main__':
    unittest.main()
