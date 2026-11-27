# 發布紀錄

版本日期使用臺灣時間。標籤指向各版正式發布時的提交，GitHub Actions 保留部署與驗證結果。

## V9.3 · 2026-11-28

- **新增** 日期切換與跨日改為預覽，實際異動才建立紀錄。新增單日及批次刪除。
- **修正** 刪除前兩次確認並列出日期。保護今日、固定編組、其他日期及顯示偏好。
- **根因** 原本選定日期直接對應儲存日期，每次瀏覽或跨日都會寫入新紀錄。
- **影響範圍** 保留所有既有紀錄、本機鍵值、版本 5 資料與備份相容性。無日期紀錄時使用可選標記保留固定編組。
- **測試** 30 項本機測試與靜態檢查通過，涵蓋日期建立與刪除、跨日競態、備份、寫入鎖、自動更新及離線。發布檢查見 GitHub Actions。
- **提交** [v9.3](https://github.com/love82214/dispatch-manager/tree/v9.3)
- **尚未實機驗證** 實體 iPhone Safari、主畫面 PWA、鍵盤與 Safe Area。

## V9.2 · 2026-11-27

- **新增** 五分頁、手機派車工作流程、排組及任務圖表、歷史清單、深色及大字體設定。
- **修正** 資料錯誤時保留原始內容、跨分頁寫入防護及全頁儲存警告。移除重繪和更新時的無條件寫入。
- **根因** 舊版將讀取或驗證失敗當成空白資料，重繪可能寫回空白結果。另一個分頁亦可能以過期資料覆蓋較新的紀錄。
- **影響範圍** 手機介面、本機儲存與復原、離線更新。保留儲存鍵值、資料結構、備份格式及 CSP。
- **測試** 六種尺寸的 Chromium 回歸、異常資料及多分頁、舊備份還原、V9.1 升級前後原始資料比對、離線重開、JavaScript 語法及差異檢查通過。
- **提交** [v9.2](https://github.com/love82214/dispatch-manager/tree/v9.2)、[PR #2](https://github.com/love82214/dispatch-manager/pull/2)、[Pages 部署](https://github.com/love82214/dispatch-manager/actions/runs/46025355125)。
- **尚未實機驗證** iPhone Safari、主畫面 PWA、實際鍵盤與 Safe Area。尚待直接核對正式網站回應。

## V9.1 · 2026-11-27

- **新增** 首次驗證 PWA 自動更新。
- **修正** 首頁「檢查程式更新」採白底深綠字。
- **根因** 更新按鈕原本從深色頁首繼承白色文字。
- **影響範圍** 更新按鈕與靜態快取 `dispatch-static-v9.1`。本機資料格式相容。
- **測試** Chromium 320、390、430 px、自動更新、離線重開、備份與資料逐位元組比對通過。
- **提交** [v9.1](https://github.com/love82214/dispatch-manager/tree/v9.1)、[PR #1](https://github.com/love82214/dispatch-manager/pull/1)、[Pages 部署](https://github.com/love82214/dispatch-manager/actions/runs/46004847893)。
- **尚未實機驗證** iPhone Safari 與主畫面 PWA。

## V9.0 · 2026-11-27

- **新增** 本機派車 PWA、離線快取與程式更新機制。
- **修正** 建立 GitHub Pages 發布基準。
- **根因** 手機需在同一網址取得新版程式並能離線使用。
- **影響範圍** 靜態 PWA 程式及本機資料操作。
- **測試** GitHub Pages 歷史部署成功。其餘歷史測試結果未留下可核對紀錄。
- **提交** [v9.0](https://github.com/love82214/dispatch-manager/tree/v9.0)、[Pages 部署](https://github.com/love82214/dispatch-manager/actions/runs/45933242403)。
- **尚未實機驗證** 無可核對的歷史實機測試紀錄。
