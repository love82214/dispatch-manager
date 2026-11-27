# 每日派車管理

本機資料專用 PWA，透過 GitHub Pages 發布。固定使用[正式網站](https://love82214.github.io/dispatch-manager/)。

## 測試

需要 Python 3.12、Node.js 24、Git 與 Playwright。GitHub Actions 在 PR 及 `main` 執行同一套檢查。

```sh
git fetch origin main --tags
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r tests/requirements.txt
python -m playwright install chromium webkit
python -m tests.static_checks --base origin/main
python -m unittest tests.test_release -v
UPGRADE_BASE_REF=origin/main BROWSER=chromium python -m unittest tests.test_browser tests.test_storage -v
UPGRADE_BASE_REF=origin/main BROWSER=webkit python -m unittest tests.test_browser tests.test_storage -v
```

Linux 缺少瀏覽器系統套件時，依 Playwright 指示安裝依賴。若環境已有相容的 Chromium，可為 Chromium 命令設定 `CHROMIUM_EXECUTABLE`。WebKit 檢查需使用 Playwright 提供的瀏覽器。測試啟動暫時的本機網站，使用虛構資料、隔離瀏覽器與前版標籤，涵蓋手機尺寸、資料安全、跨日、舊版升級、離線及不支援 Web Locks 的行為。WebKit 測試不等同實體 iPhone 驗收。

開發規範見 [AGENTS.md](AGENTS.md)。版本資訊見 [VERSION.json](VERSION.json)、[CHANGELOG.md](CHANGELOG.md) 及 [發布與回復手冊](RELEASING.md)。
