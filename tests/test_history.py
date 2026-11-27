"""Date previews, deliberate record creation and checked history deletion."""
import json
from datetime import timedelta

from playwright.sync_api import expect

from tests.browser_support import (
    DENY_WRITES, FIXTURE, FIXTURE_TEXT, KEY, NOW, ROSTER, TODAY, TOMORROW, YESTERDAY,
    BrowserCase, get_download, hold_write_lock, navigate, persisted, restore, stored_text,
    wait_for, wait_for_writes, warn,
)

OLDER = (NOW.date() - timedelta(days=2)).isoformat()
PREFERENCES = 'dispatch-mobile-v92-ui'


def open_date(page, date):
    page.locator('#workDate').fill(date)
    expect(page.locator('#workDate')).to_have_value(date)


def stored_dates(page):
    return set(page.locator('#historyList [data-date]').evaluate_all('buttons => buttons.map(b => b.dataset.date)'))


def review_dates(page, dates):
    expect(page.locator('#deleteDatesDialog')).to_be_visible()
    expect(page.locator('#deleteDatesStep')).to_contain_text('第 1 次確認')
    expect(page.locator('#deleteDatesList li')).to_have_text(sorted(dates, reverse=True))
    expect(page.locator('#confirmDeleteDates')).to_be_hidden()
    page.locator('#reviewDeleteDates').click()
    expect(page.locator('#deleteDatesStep')).to_contain_text('第 2 次確認')
    expect(page.locator('#deleteDatesList li')).to_have_text(sorted(dates, reverse=True))


class DateHistory(BrowserCase):
    def test_first_visit_and_date_switch_only_preview(self):
        with self.app() as (page, _):
            expect(page.locator('#recordStatus')).to_contain_text('尚未建立紀錄')
            page.locator('#nextDate').click()
            expect(page.locator('#workDate')).to_have_value(TOMORROW)
            open_date(page, YESTERDAY)
            page.reload()
            expect(page.locator('#workDate')).to_have_value(YESTERDAY)
            expect(page.locator('#recordStatus')).to_be_visible()
            navigate(page, 'records')
            expect(page.locator('#historyList')).to_contain_text('尚無已儲存的日期紀錄')
            self.assertIsNone(stored_text(page))

    def test_preview_save_without_change_and_reset_do_not_create(self):
        with self.app(seed=FIXTURE_TEXT) as (page, _):
            open_date(page, TOMORROW)
            navigate(page, 'dispatch')
            expect(page.locator('#list')).to_contain_text('虛構固定備註')
            expect(page.locator('#recordStatus')).to_be_visible()
            page.locator('[data-edit]').click()
            expect(page.locator('#restoreCar')).to_be_hidden()
            page.locator('#editForm footer button').click()
            expect(page.locator('#editor')).to_be_hidden()
            self.assertEqual(stored_text(page), FIXTURE_TEXT)
            navigate(page, 'records')
            _, report = get_download(page, '#export')
            self.assertTrue(report.decode('utf-8-sig').startswith('尚未建立紀錄'))
            expect(page.locator(f'[data-date="{TOMORROW}"]')).to_have_count(0)
            navigate(page, 'settings')
            expect(page.locator('#reset')).to_be_disabled()
            self.assertEqual(stored_text(page), FIXTURE_TEXT)

    def test_pinned_preview_can_resume_following_today_after_midnight(self):
        with self.app(seed=FIXTURE_TEXT, time=NOW.replace(hour=23, minute=58), ticking=True) as (page, _):
            open_date(page, TOMORROW)
            page.clock.fast_forward(125000)
            expect(page.locator('#dateHint')).to_have_text('今天')
            expect(page.locator('#recordStatus')).to_be_visible()
            page.reload()
            expect(page.locator('#goToday')).to_be_enabled()
            page.locator('#goToday').click()
            expect(page.locator('#goToday')).to_be_disabled()
            self.assertEqual(stored_text(page), FIXTURE_TEXT)

    def test_checkbox_task_and_applied_import_create_only_the_edited_date(self):
        with self.app(seed=FIXTURE_TEXT) as (page, _):
            open_date(page, TOMORROW)
            navigate(page, 'dispatch')
            page.locator('[data-check]').click()
            expect(page.locator('#recordStatus')).to_be_hidden()
            self.assertTrue(persisted(page)['history'][TOMORROW][0]['checked'])
            self.assertEqual(persisted(page)['date'], TODAY)
            self.assertEqual(persisted(page)['rows'], FIXTURE['rows'])

            open_date(page, '2024-03-02')
            page.locator('[data-edit]').click()
            page.locator('#eTaskChoice').select_option('custom')
            page.locator('#eTaskCustom').fill('虛構新增任務')
            page.locator('#editForm footer button').click()
            expect(page.locator('#recordStatus')).to_be_hidden()
            self.assertEqual(persisted(page)['history']['2024-03-02'][0]['task'], '虛構新增任務')
            self.assertEqual(persisted(page)['base'], FIXTURE['base'])

            open_date(page, '2024-03-03')
            page.locator('#importPanel summary').click()
            page.locator('#source').fill(ROSTER)
            page.locator('#parse').click()
            expect(page.locator('#parseResult')).to_contain_text('辨識 5 輛')
            before = stored_text(page)
            page.once('dialog', lambda dialog: dialog.dismiss())
            page.locator('#apply').click()
            self.assertEqual(stored_text(page), before)
            page.once('dialog', lambda dialog: dialog.accept())
            page.locator('#apply').click()
            expect(page.locator('#recordStatus')).to_be_hidden()
            self.assertEqual(len(persisted(page)['history']['2024-03-03']), 5)
            for date, rows in FIXTURE['history'].items():
                self.assertEqual(persisted(page)['history'][date], rows)

    def test_single_delete_requires_both_confirmations_and_stays_deleted(self):
        with self.app(seed=FIXTURE_TEXT, width=320) as (page, _):
            navigate(page, 'settings')
            page.locator('#theme').select_option('dark')
            page.locator('#fontSize').select_option('large')
            navigate(page, 'records')
            page.locator(f'[data-date="{YESTERDAY}"]').click()
            preferences = page.evaluate('(key) => localStorage.getItem(key)', PREFERENCES)
            page.locator(f'[data-preview-date="{YESTERDAY}"]').click()
            expect(page.locator('#historyText')).to_contain_text('虛構歷史備註1')
            button = page.locator(f'[data-delete-date="{YESTERDAY}"]')
            button.click()
            expect(page.locator('#deleteDatesStep')).to_contain_text('第 1 次確認')
            page.locator('#cancelDeleteDates').click()
            expect(page.locator('#deleteDatesDialog')).to_be_hidden()
            self.assertEqual(stored_text(page), FIXTURE_TEXT)

            button.click()
            review_dates(page, [YESTERDAY])
            page.locator('#cancelDeleteDates').click()
            expect(page.locator('#deleteDatesDialog')).to_be_hidden()
            self.assertEqual(stored_text(page), FIXTURE_TEXT)

            button.click()
            review_dates(page, [YESTERDAY])
            page.locator('#confirmDeleteDates').click()
            expect(page.locator('#toast')).to_contain_text('已刪除 1 筆')
            expect(page.locator('#historyText')).to_be_hidden()
            expect(page.locator('#workDate')).to_have_value(YESTERDAY)
            expect(page.locator('#recordStatus')).to_be_visible()
            self.assertEqual(persisted(page), dict(FIXTURE, history={OLDER: FIXTURE['history'][OLDER]}))
            self.assertEqual(page.evaluate('(key) => localStorage.getItem(key)', PREFERENCES), preferences)
            after = stored_text(page)
            page.reload()
            expect(page.locator('#workDate')).to_have_value(YESTERDAY)
            expect(page.locator('#recordStatus')).to_be_visible()
            page.locator('#goToday').click()
            page.locator('#prevDate').click()
            navigate(page, 'records')
            self.assertEqual(stored_dates(page), {TODAY, OLDER})
            expect(page.locator('#historyTitle')).to_be_visible()
            self.assertEqual(stored_text(page), after)

    def test_batch_deletion_can_remove_primary_slot_but_never_today(self):
        original = dict(FIXTURE, date=YESTERDAY, rows=FIXTURE['history'][YESTERDAY],
                        history={TODAY: FIXTURE['rows'], OLDER: FIXTURE['history'][OLDER],
                                 TOMORROW: FIXTURE['rows']})
        with self.app(seed=json.dumps(original, ensure_ascii=False)) as (page, _):
            navigate(page, 'records')
            expect(page.locator(f'[data-select-date="{TODAY}"]')).to_have_count(0)
            expect(page.locator(f'[data-delete-date="{TODAY}"]')).to_have_count(0)
            expect(page.locator('#deleteSelectedDates')).to_be_disabled()
            for date in (YESTERDAY, TOMORROW):
                page.locator(f'[data-select-date="{date}"]').check()
            expect(page.locator('#selectedDateCount')).to_have_text('已選 2 筆')
            page.locator('#deleteSelectedDates').click()
            review_dates(page, [YESTERDAY, TOMORROW])
            page.locator('#confirmDeleteDates').click()
            expect(page.locator('#toast')).to_contain_text('已刪除 2 筆')
            self.assertEqual(stored_dates(page), {TODAY, OLDER})
            self.assertEqual(persisted(page), dict(FIXTURE, history={OLDER: FIXTURE['history'][OLDER]}))
            navigate(page, 'settings')
            expect(page.locator('#reset')).to_be_enabled()

    def test_delete_last_record_survives_reload_and_backup_round_trip(self):
        seed = dict(FIXTURE, date=YESTERDAY, rows=[], history={})
        with self.app(seed=json.dumps(seed)) as (page, _):
            navigate(page, 'records')
            self.assertEqual(stored_dates(page), {YESTERDAY})
            page.locator(f'[data-delete-date="{YESTERDAY}"]').click()
            review_dates(page, [YESTERDAY])
            page.locator('#confirmDeleteDates').click()
            expect(page.locator('#historyList')).to_contain_text('尚無已儲存的日期紀錄')
            self.assertEqual(persisted(page)['base'], FIXTURE['base'])
            self.assertEqual(persisted(page)['version'], 5)
            after_delete = stored_text(page)
            page.reload()
            navigate(page, 'settings')
            _, backup = get_download(page, '#backup')
            restore(page, backup, accept=True)
            expect(page.locator('#toast')).to_have_text('已還原備份')
            self.assertEqual(stored_text(page), after_delete)
            open_date(page, YESTERDAY)
            navigate(page, 'records')
            self.assertEqual(stored_dates(page), set())
            navigate(page, 'dispatch')
            page.locator('[data-check]').click()
            expect(page.locator('#recordStatus')).to_be_hidden()
            navigate(page, 'records')
            self.assertEqual(stored_dates(page), {YESTERDAY})
            self.assertEqual(persisted(page)['history'], {})

    def test_legacy_empty_saved_day_is_preserved_when_other_dates_are_deleted(self):
        # An older reader can leave the optional marker while writing dated data.
        seed = dict(FIXTURE, rows=[], history={YESTERDAY: FIXTURE['history'][YESTERDAY]},
                    noDateRecords=True)
        with self.app(seed=json.dumps(seed)) as (page, _):
            navigate(page, 'records')
            self.assertEqual(stored_dates(page), {TODAY, YESTERDAY})
            page.locator(f'[data-delete-date="{YESTERDAY}"]').click()
            review_dates(page, [YESTERDAY])
            page.locator('#confirmDeleteDates').click()
            expect(page.locator('#toast')).to_contain_text('已刪除 1 筆')
            self.assertEqual(stored_dates(page), {TODAY})
            expect(page.locator('#recordStatus')).to_be_hidden()
            self.assertEqual(persisted(page)['rows'], [])

    def test_queued_checkbox_at_midnight_does_not_edit_either_day(self):
        with self.app(seed=FIXTURE_TEXT, time=NOW.replace(hour=23, minute=58), ticking=True) as (page, _):
            navigate(page, 'dispatch')
            with hold_write_lock(page):
                page.locator('[data-check]').click()
                wait_for_writes(page, 1)
                page.clock.fast_forward(125000)
            expect(page.locator('#workDate')).to_have_value(TOMORROW)
            expect(page.locator('#recordStatus')).to_be_visible()
            self.assertEqual(stored_text(page), FIXTURE_TEXT)

    def test_delete_batch_aborts_when_waiting_date_becomes_today(self):
        seed = dict(FIXTURE, history={**FIXTURE['history'], TOMORROW: FIXTURE['rows']})
        raw = json.dumps(seed)
        with self.app(seed=raw, time=NOW.replace(hour=23, minute=58), ticking=True) as (page, _):
            navigate(page, 'records')
            for date in (YESTERDAY, TOMORROW):
                page.locator(f'[data-select-date="{date}"]').check()
            page.locator('#deleteSelectedDates').click()
            review_dates(page, [YESTERDAY, TOMORROW])
            with hold_write_lock(page):
                page.locator('#confirmDeleteDates').click()
                wait_for_writes(page, 1)
                page.clock.fast_forward(125000)
            expect(page.locator('#deleteDatesDialog')).to_be_hidden()
            expect(page.locator('#toast')).to_contain_text('今日紀錄不能刪除')
            self.assertEqual(stored_text(page), raw)
            expect(page.locator(f'[data-delete-date="{TOMORROW}"]')).to_have_count(0)
            expect(page.locator(f'[data-delete-date="{TODAY}"]')).to_be_visible()

    def test_cancel_during_lock_wait_does_not_delete(self):
        with self.app(seed=FIXTURE_TEXT) as (page, _):
            navigate(page, 'records')
            page.locator(f'[data-delete-date="{YESTERDAY}"]').click()
            review_dates(page, [YESTERDAY])
            with hold_write_lock(page):
                page.locator('#confirmDeleteDates').click()
                wait_for_writes(page, 1)
                page.locator('#cancelDeleteDates').click()
                expect(page.locator('#deleteDatesDialog')).to_be_hidden()
            page.evaluate('key => navigator.locks.request(key, () => {})', KEY)
            self.assertEqual(stored_text(page), FIXTURE_TEXT)

    def test_stale_confirmation_does_not_delete_another_tabs_changes(self):
        with self.app(seed=FIXTURE_TEXT) as (first, context):
            other = context.new_page()
            other.goto(self.server.url)
            navigate(first, 'records')
            first.locator(f'[data-delete-date="{YESTERDAY}"]').click()
            review_dates(first, [YESTERDAY])
            navigate(other, 'dispatch')
            other.locator('[data-check]').click()
            wait_for(lambda: not persisted(other)['rows'][0]['checked'], 'Second tab did not save')
            first.locator('#confirmDeleteDates').click()
            expect(first.locator('#deleteDatesDialog')).to_be_hidden()
            warn(first, '另一個分頁已變更')
            self.assertEqual(persisted(other)['history'], FIXTURE['history'])

    def test_delete_failure_does_not_partially_remove_a_batch(self):
        with self.app(seed=FIXTURE_TEXT, init=DENY_WRITES) as (page, _):
            navigate(page, 'records')
            for date in (YESTERDAY, OLDER):
                page.locator(f'[data-select-date="{date}"]').check()
            page.locator('#deleteSelectedDates').click()
            review_dates(page, [YESTERDAY, OLDER])
            page.locator('#confirmDeleteDates').click()
            expect(page.locator('#deleteDatesDialog')).to_be_hidden()
            warn(page, '本機儲存失敗')
            self.assertEqual(stored_text(page), FIXTURE_TEXT)
            self.assertEqual(stored_dates(page), {TODAY, YESTERDAY, OLDER})
