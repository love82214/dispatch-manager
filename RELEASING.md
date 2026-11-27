# 發布與回復手冊

## 準備版本

若 PR 修改了任一離線資源或 `sw.js`，以目前 `main` 為基礎使用下一個版本號。版本工具會一併更新 `VERSION.json`、首頁和設定標示、程式通知、Service Worker 快取名稱及版本紀錄。例示參數應換成本次實際內容。

```sh
python -m scripts.release prepare 9.2.1 \
  --summary '本次新增內容' --fixes '本次修正' --cause '問題根因' \
  --impact '影響範圍及相容性' --tests '已通過的測試及結果' \
  --unverified '尚未實機驗證的項目'
```

預設使用臺灣當日日期，也可指定 `--date YYYY-MM-DD`。合併前檢查日期與紀錄，補上實際檢查結果和必要的提交或 PR 連結。單純維護文件、發布流程或測試時，不需變更應用程式版本。

## 合併及驗證

1. 依 [AGENTS.md](AGENTS.md) 校驗資料安全和程式差異，執行 [測試](README.md#測試)，建立 PR。確認 GitHub Actions 的 **Release gate** 和現有必要檢查皆成功，且指向當前 PR head 與基底。
2. 使用有權限的 GitHub 連線，以預期 head SHA 合併至 `main`。例如使用已授權的 GitHub CLI 時，可執行 `gh pr merge <PR> --merge --match-head-commit <HEAD_SHA>`。一般發布不需額外確認，仍須遵守分支規則。自動化工作只在 `main` 寫入版本標籤。PR 本身的測試工作採唯讀權限。
3. 既有 GitHub Pages 從 `main` 部署到 [原網址](https://love82214.github.io/dispatch-manager/)。確認 **pages build and deployment** 成功。**Verify GitHub Pages and tag release** 等待相同提交的部署並直接比對正式站回應。它會核對首頁、版本 JSON、Service Worker 及每個離線資源，成功後才為新版本建立 Git 標籤，並在 Actions 摘要記錄日期、提交及驗證結果。相同版本的維護部署會保留既有標籤。
4. 若驗證失敗，確認可否重跑該提交的工作。需要驗證當前 `main` 時也可手動執行 **Regression and release**。直接從工作環境比對正式網站可使用 `python -m scripts.verify_pages --check-site-only`。無法取得公開回應時，保留部署紀錄並標明正式網站尚未驗證。不得以本機或 GitHub 原始碼冒充網站回應。
5. iPhone 實機需核對 Safari、主畫面 PWA、Safe Area、鍵盤操作、更新與離線。由 V9.1 升級時先關閉其他仍執行舊版的分頁，舊分頁不受 V9.2 的 Web Locks 防護。

## 安全回復與緊急修正

1. 比對有問題的版本標籤及上一個穩定標籤，找出要修復或反轉的變更。從目前 `main` 開緊急修正分支，選擇性恢復已知穩定行為，保留已修復的本機資料和安全防護。
2. 建立高於故障版本的新修正版。例如 V9.3 有問題時，可在 V9.3.1 恢復 V9.2 的相關行為。保留故障與穩定版本的標籤及提交。既有 Service Worker 快取名稱不得重用。
3. 從正在發布的版本測試自動升級至緊急修正版，驗證既有紀錄與備份、離線、跨日及多分頁。用相同 PR 檢查、合併、部署驗證與標籤流程發布。
4. 異常資料留在裝置，使用本機復原流程。不得為回復程式版本而清除瀏覽器站點資料、刪除手機紀錄、回寫空白或停用資料保護。
