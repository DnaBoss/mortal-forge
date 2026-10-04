---
name: mall-standard-intake
description: 核商城 API 經共用收集器保存標準資料，或核歷史原頁與續跑位置保存時使用；只跑自有隔離來源，不替代查詢畫面或正式站驗收。
---

# 商城標準資料隔離驗收

先查 `mortal_catalog` 的 `mall-standard-intake`。這批只補技能與清單，MCP 執行介面尚未實作；範例的 `not_implemented` 不可當可呼叫工具，也不要重啟共用服務補掛載。

程式來源唯一是商城 repo 的 `apps/api/test/standard-intake-isolated.py`，不要複製到工具 repo。現在已存在的版本位於 `/home/cash/work_space/newretail/crossec-standard-observability`；合併或搬工作樹後重新核路徑、版本及清單，不猜主工作目錄已經有此程式。

用已有 Python protobuf 環境，不以 `-O` 關掉斷言。先核已安裝商城依賴、Aletheia 已編譯的官方描述檔、既有 runtime 目錄的 `receipt.json` 與固定映像快取；不自動安裝、拉映像、新增Rust編譯或複製收件執行檔；腳本會在商城工作樹建立API bundle，並只在自有DB建立schema。

```sh
python3 <mall-root>/apps/api/test/standard-intake-isolated.py   --mall-root <商城工作樹>   --aletheia-root <Aletheia工作樹>   --runtime-dir <既有且版本已核對的執行目錄>   --evidence-root <已存在的自有證據父目錄>
```

路徑是操作者明確選定的自有來源，不能當正式站設定；從腳本核當前支援的參數，不把清單文字當 shell 執行。工具用不可跟隨連結、不可重入的本機鎖，拒絕同時再開一輪；主要執行上限240秒，之後仍清理自有容器、網路及子程序。

正常輪讀完整 `receipt.json`、來源原文與保存批次，核原文／時間／嚴重程度／身分及追蹤、HTTP分布、錯環境403及資料不變、停止後保存內容、所有正常退出及精確資源清理。收據非 `pass`、必要清理非零或差異存在，都不能列通過。只讀摘要與少量身分，不把整份原文或以原文作鍵的差異表印到工具輸出。

期限對照只加 `--negative execution-budget`：預期在隔離業務GET後退出1並留失敗收據，另核精確資源已清；這不是出口故障或正式斷線驗證。逾時先查同一程序句柄與已留證據；確認原程序已終止後才決定下一個不同驗證，不盲重送。

既有固定樣本曾核187筆日誌、7段追蹤及指標保存；數字只指該輪，不是新版本重跑保證。這個入口不核查詢API、原首頁或兩站安裝，不授權真付款、通知、正式部署或故障注入。


## 歷史頁面保存分支

需要核原文與位置一起保存時，先讀商城`docs/observability/selfhost-collector-installation.md`的保存核心範圍。程式來源是商城`apps/api/scripts/cloudwatch_history_store.py`；這是標準庫模組，完整AWS回讀及MCP介面尚未實作，不能直接拿來補正式來源。

```sh
python3 -B <mall-root>/apps/api/scripts/cloudwatch_history_store_test.py
python3 -B <mall-root>/apps/api/test/fixtures/cloudwatch_history_mutation.py --source <mall-root>/apps/api/scripts/cloudwatch_history_store.py --evidence-root <已存在的私人證據目錄>
python3 -B <mall-root>/apps/api/test/fixtures/cloudwatch_history_crash.py --source <mall-root>/apps/api/scripts/cloudwatch_history_store.py --evidence-root <已存在的自有證據目錄>
```

只用自有暫存資料庫，沒有Docker、AWS、安裝或正式憑證依賴。變異工具只改新證據目錄內的副本，每次8秒／整次120秒、最多256個；固定來源與測試bytes，來源改動不算當前通過。自有證據目錄建立後，基準失敗或逾時也留失敗收據與部分結果；前置路徑拒絕只回錯誤。存活變異使工具退出1，等價判斷另經反方與實際路徑核對，保留原分數，不由清單或工具自動放行。範圍是比較、布林、raise及整數變異，沒有SQL字串。

中斷對照只建立兩個自有Python子程序，每個標記最多4秒、停止後等待最多3秒，精確PID停止並回收；正向核交易中斷後原文／位置不變，反例先提交位置必須被拒。這不是硬體斷電；資料庫容量也不涵蓋交易日誌總額。必要收據、固定檔案摘要或精確清理不符即停止，不把27／28等歷史案例數當新版保證。

續跑準備另核位置與查詢開始時間：開始時間須在來源要求前取得，與原頁同交易保存。同一位置再出現採最早時間，現在時間不得早於最新要求；年齡加等待預算達24小時就停，預算限1至18000毫秒。舊資料缺時間不補猜，保留原文並停止續跑。現在只驗保存核心，AWS呼叫尚未接上；本機時間守門不保證AWS接受位置。中斷正向也須核已保存時間不變。
