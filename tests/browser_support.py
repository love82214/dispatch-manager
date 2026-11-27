"""Isolated local origin, synthetic records and shared browser assertions."""
import json
import os
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from time import monotonic, sleep

from playwright.sync_api import expect, sync_playwright

from scripts.release import ROOT, release_info

ENGINE = os.environ.get('BROWSER', 'chromium')
KEY = 'dispatch-mobile-v5-local'
INFO = release_info()
VERSION = INFO['version']
PREVIOUS = INFO['previousVersion']
TAIPEI = timezone(timedelta(hours=8))
NOW = datetime(2024, 2, 29, 12, tzinfo=TAIPEI)
TODAY = NOW.date().isoformat()
YESTERDAY = (NOW.date() - timedelta(days=1)).isoformat()
TOMORROW = (NOW.date() + timedelta(days=1)).isoformat()
VIEWS = ('overview', 'dispatch', 'statistics', 'records', 'settings')
FICTIONAL_ROW = {
    'id': '軍T-00000', 'unit': '虛構測試組', 'status': '正常派車',
    'captain': '虛構車長', 'driver': '虛構駕駛', 'task': '虛構任務',
    'note': '虛構固定備註', 'checked': False,
}
FIXTURE = {
    'version': 5, 'date': TODAY, 'base': [FICTIONAL_ROW],
    'rows': [dict(FICTIONAL_ROW, checked=True, note='虛構今日備註')],
    'history': {
        (NOW.date() - timedelta(days=i)).isoformat(): [
            dict(FICTIONAL_ROW, checked=i == 1, task=f'虛構歷史任務{i}', note=f'虛構歷史備註{i}')
        ] for i in (1, 2)
    },
}
FIXTURE_TEXT = json.dumps(FIXTURE, ensure_ascii=False)
ROSTER = """虛構甲組
☑ 軍1-00000 虛構甲、虛構乙 任務：人員載運 備註：虛構備註
軍2-00000 虛構丙、虛構丁
虛構乙組
軍3-00000 另有任務 任務：救護待命
軍8-00000 空車
軍T-00000 待命"""


class AppServer(ThreadingHTTPServer):
    def __init__(self):
        super().__init__(('127.0.0.1', 0), AppHandler)
        self.directory = ROOT
        self.reachable = True
        self.url = f'http://127.0.0.1:{self.server_port}/dispatch-manager/'


class AppHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=args[2].directory, **kwargs)

    def translate_path(self, path):
        return super().translate_path(path.removeprefix('/dispatch-manager'))

    def do_GET(self):
        if not self.server.reachable:
            self.close_connection = True
            return
        super().do_GET()

    def send_head(self):
        # Both revisions share one URL. Directory timestamps do not represent deploy order.
        del self.headers['If-Modified-Since']
        return super().send_head()

    def end_headers(self):
        self.send_header('Cache-Control', 'no-cache')
        super().end_headers()

    def log_message(self, *_):
        pass


def wait_for(predicate, message, timeout=18):
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        if predicate():
            return
        sleep(.15)
    raise AssertionError(message)


def navigate(page, view):
    page.locator(f'[data-view="{view}"]').click()
    expect(page.locator('#' + view)).to_be_visible()


def stored_text(page):
    return page.evaluate('(key) => localStorage.getItem(key)', KEY)


def persisted(page):
    return json.loads(stored_text(page))


def get_download(page, button):
    with page.expect_download() as event:
        page.locator(button).click()
    download = event.value
    name, body = download.suggested_filename, download.path().read_bytes()
    download.delete()
    return name, body


def restore(page, data, accept=None):
    if accept is not None:
        page.once('dialog', lambda dialog: dialog.accept() if accept else dialog.dismiss())
    page.locator('#backupFile').set_input_files({
        'name': 'fixture-only.json', 'mimeType': 'application/json', 'buffer': data
    })
    expect(page.locator('#backupFile')).to_have_value('')


def wait_cache(page, version):
    wait_for(lambda: page.evaluate("""async version => {
      const names = (await caches.keys()).filter(name => name.startsWith('dispatch-static-'));
      return !!navigator.serviceWorker.controller && names.length === 1 && names[0] === version;
    }""", f'dispatch-static-v{version}'), f'Expected active worker and only cache V{version}')


def warn(page, message):
    expect(page.locator('#storageBanner')).to_be_visible()
    expect(page.locator('#storageMessage')).to_contain_text(message)


def assert_stats(page, total):
    vehicle = page.locator('#typeChart progress').evaluate_all('(bars) => bars.map(bar => bar.value)')
    tasks = page.locator('#taskStats progress').evaluate_all('(bars) => bars.map(bar => bar.value)')
    table = [int(value) for value in page.locator('#stats tfoot td').all_text_contents()]
    assert vehicle == table[:-1] and sum(vehicle) == sum(tasks) == table[-1] == total


class BrowserCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = AppServer()
        server_thread = Thread(target=cls.server.serve_forever, daemon=True)
        server_thread.start()
        cls.addClassCleanup(cls.server.server_close)
        cls.addClassCleanup(cls.server.shutdown)
        playwright = sync_playwright().start()
        cls.addClassCleanup(playwright.stop)
        binary = os.environ.get('CHROMIUM_EXECUTABLE') if ENGINE == 'chromium' else None
        cls.browser = getattr(playwright, ENGINE).launch(executable_path=binary)
        cls.addClassCleanup(cls.browser.close)

    @contextmanager
    def app(self, *, width=390, seed=None, init='', previous=None, time=NOW, ticking=False):
        self.server.directory = previous or ROOT
        context = self.browser.new_context(
            viewport={'width': width, 'height': 844}, is_mobile=width < 768,
            has_touch=width < 768, locale='zh-TW', timezone_id='Asia/Taipei'
        )
        errors = []
        context.on('page', lambda page: page.on('pageerror', lambda error: errors.append(str(error))))
        context.add_init_script(f'''(() => {{
          if (location.origin !== new URL({json.dumps(self.server.url)}).origin) return;
          const key = {json.dumps(KEY)};
          const seed = {json.dumps(seed)};
          if (seed !== null && localStorage.getItem(key) === null) localStorage.setItem(key, seed);
          {init}
        }})();''')
        try:
            page = context.new_page()
            if ticking:
                page.clock.install(time=time)
            else:
                page.clock.set_fixed_time(time)
            page.goto(self.server.url)
            yield page, context
            self.assertEqual(errors, [], 'Uncaught browser errors')
        finally:
            context.close()
            self.server.directory = ROOT
            self.server.reachable = True
