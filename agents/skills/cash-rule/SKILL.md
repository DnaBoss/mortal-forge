---
name: cash-rule
description: 建立或接手單一長任務，先查重既有卡、loop、分支與 PR，再以證據循環推進到整體驗收或明確終止。適用於使用者明確要求 cash-rule、longrun 或跨輪持續執行；短任務不用。
---

# cash-rule：單一長任務執行協定

Protocol version: `1.3.1`. 使用者當前指示與專案規則優先；本協定不增加任何授權。原文封存於 `../../archive/burden-cut-20261015/rules/cash-rule/`。

## 啟動與接手

輸入可為任務描述、ticket、既有 loop 檔或 slug。先依序查 `loops/`、issue／看板、`feature/<slug>` 分支及未合併 PR；找到同一工作就接手，全部沒有才依專案規則建立卡、loop 與分支。不得為同一工作開第二張卡、第二份 loop 或平行分支。

新 loop 至少記錄目標、整體驗收、已知、來源、計畫、目前狀態與下一步；分支基準、看板、守門與合併規則以 workspace 規範為準。接手時從既有「下一步」與最近證據繼續，不重做已通過項目。

執行者負責最後決策。若指定 `--reviewer codex|claude`，在計畫定案及改動完成時請可用的另一模型做反方審查；意見只供參考，裁決順序是使用者決策、workspace 規範、直接證據。未指定或 reviewer 不可用時不阻塞主線，記錄原因即可。

長任務預設每 5 分鐘續跑一次。使用宿主提供的 recurring task／continuation；宿主沒有續跑能力時不得假裝背景執行，完成本輪後留下可直接接續的下一步。每輪必須產生新證據、完成一個可驗收切片或明確記錄阻塞；不能只重報未變狀態。

## 生命週期

唯一循環：`Inspect → Plan → Execute → Validate → Review/Replan → Checkpoint`。

- Inspect：盤點現況、產物、限制與未知，不假設。
- Plan：寫目標、整體驗收、主要 step、風險、停止條件；只細拆近期一至兩步。
- Execute：每輪推進一個主要 step，走已知最短的路（使用者 2026-10-05 定）。
- Validate：用實際執行結果；單元測試不替代整體驗收。
- Review/Replan：依新證據重排，不重做已通過的工作。
- Checkpoint：只在狀態變化或有新證據時寫（使用者 2026-10-15 定）。

任務狀態：`DISCOVERING`、`PLANNED`、`RUNNING`、`VALIDATING`、`REVIEWING`、`WAITING`（等具名的人或事件）、`BLOCKED`、`MONITORING`；終態 `COMPLETE`／`CANCELLED`／`SUPERSEDED`／`FAILED`，只有整體驗收通過才 `COMPLETE`。Step 狀態：`PENDING`、`READY`、`RUNNING`、`VALIDATING`、`DONE`、`BLOCKED`、`FAILED`、`CANCELLED`、`SKIPPED`、`SUPERSEDED`；未驗收不得 `DONE`。合法轉換由 schema 與寫入工具把關，不在這裡重述。

## 交付點與不停工（使用者 2026-10-17 定）

階段、大功能、里程碑都是交付點。規劃時列入同名 `*.delivery.json`；內部分析／準備步驟須明列理由，不得把交付點改名藏掉。交付點寫 `VALIDATING` 並附全部通過的檢查時，進度工具自動送出既有授權的背景部署；AI 立即繼續無依賴工作。部署與線上驗收未過，不得將該交付點標 `DONE` 或整體標 `COMPLETE`，但不得因此停下其他工作。不得以「部署中」為由反覆等待或重送；查明狀態，修復或續做其他步驟。細則、部署接法與恢復見 [交付](references/delivery-policy.md)。

任務實作完成且基本品質驗證通過後，只要既有授權涵蓋推版與部署，就預設立即提交、推送、合併、部署並讀回線上版本；不得因為尚缺只能在部署後取得的正式旁路或實機數據而停在 PR。這類數據應先用不改真實決策的安全模式部署後取得，再決定是否啟用。只有品質或合併閘門失敗、明確安全風險、會中斷進行中的工作，或缺少必要授權時才暫停，並寫清楚阻擋證據與可執行的下一步。（使用者 2026-10-21 定）

## 瀏覽器跨版交付（2026-10-18）

網頁發布須同時驗新版入口、升級前入口仍開著的情況、原網址正常重新整理、舊資源可讀及故意缺檔的失敗對照；不得用清快取或加查詢參數代替原網址驗收。保留舊入口相依資源，確認入口快取規則；僅健康端點、版本檔、下載雜湊不算可玩。收據標 `surface:browser`，附四份同版原件；格式及機械檢查見 [交付](references/delivery-policy.md)。

## 每輪三問（使用者 2026-10-09 定）

1. 更接近目標了嗎：對照整體驗收列本輪新證據；改檔數、工具呼叫數、局部測試數不算進度。
2. 走的是目前最佳路徑嗎：在已知、可行、已授權的路中選最直接的一條。
3. 走偏了嗎：在做無關功能、過度補文件、重複驗證，立刻停下拉回。

連續兩輪沒有新證據就換方法、縮小問題或提出決策，不重跑原命令。

原始交付決定範圍；每個旁支必須能指出不做就無法交付的原始要求，否則不阻擋主線。使用者糾正方向時先更新當前步驟，不得回答後又恢復被否定的做法。只剩背景工作時等待該工作的完成事件；重讀未變日誌、寫進度或重複回報不算進展，不觸發新一輪。

## 證據

重要結論連到命令輸出、測試名、檔案路徑與版本。有驗過直接講死並附來源；沒驗過寫「未查證」；講證據同時講邊界。註解、文件、commit 訊息、他人報告描述的是意圖不是行為，引用前先驗證。結果照實報，沒跑的檢查主動講。

## 授權與不停下（使用者 2026-10-03 定）

不自行增加授權；不假裝通過（不放寬測試、不刪驗證、不用「完成」文字代替交付）；不改寫使用者原始資料。手上有事就不停：卡死的是必要 step 才當場停；非必要 step 卡住先做別的，最後再試一次。只是取捨就自己決定；拿不定主意就上網查最佳做法或問另一個 AI；等人只在缺授權或重大選擇（使用者 2026-10-15 定）。不花使用者的錢、不調機器規格。

## 停止

只有三種：整體驗收全過標 `COMPLETE`；做不到（要有「死在哪一步」的直接證據，且換過方法）；缺人類決定（只缺授權或選擇）。停止前交 [停止舉證](references/stop-policy.md)；等人時停排程、不喚醒。

## 紀錄與回報

- 一任務一份 LOOP，整檔不超過 3,000 字元（範本 [task.loop.md](templates/task.loop.md)）：目標、整體驗收、計畫表、目前狀態。歷史進 checkpoint JSONL，只准經 `~/tools/cash-rule-checkpoint` 寫入（細則 [紀錄](references/reporting.md)）。短任務不建檔。
- 對人回報只有四件事：目標一句、做法一句、每個 step 一句成果、重大事件一行。

## 本機 Essence（使用者 2026-09-28 定）

工作派本機 AI 執行、監督者驗收；開工先讀 lessons；可重用程式做成 SKILL＋MCP 進 mortal-mcp；CPU／記憶體留餘裕。Rust 一個 repo 只有一份 `target/`（使用者 2026-10-03／04 定），由 `~/.local/bin/cargo` 包裝程式與 guard 執行，細則見 cargo-cache 技能。

Shell 指令中的 `*`、`?` 必須加引號，或改用 `find`、`rg --glob`；不能用 `GLOB_OK=1` 掩蓋可改正的指令。這項檢查只適用真正的 shell 指令，不得掃描補丁內容；Python 的 keyword-only `*,` 等程式語法必須放行。`write_guard.py` 依工具名稱分流，`test_shell_glob.py` 同時驗證補丁放行與 shell 攔截。

## 按需載入

[工程政策](references/engineering-policy.md)、[評估](references/evaluation-policy.md)、[派工](references/model-dispatch.md)、[停止舉證](references/stop-policy.md)、[執行與看門狗](references/runtime.md)、[交付](references/delivery-policy.md)、[背景](references/context-policy.md)、[紀錄](references/reporting.md)。
