---
name: cash-rule
description: 建立或接手單一長任務（一次一張 ticket、進度隨狀態更新），先查重既有卡、loop、分支與 PR，再以證據循環推進到整體驗收或明確終止。評估為大型、多步或需跨輪完成的工作時自動適用，使用者要求 cash-rule 或 longrun 時也適用；單輪可完成的短任務不用。
---

# cash-rule：單一長任務執行協定

Protocol version: `1.3.1`. 使用者當前指示與專案規則優先；本協定不增加任何授權。原文封存於 `../../archive/burden-cut-20261015/rules/cash-rule/`。

## 啟動與接手

輸入可為任務描述、ticket、既有 loop 檔或 slug。先依序查 `loops/`、issue／看板、`feature/<slug>` 分支及未合併 PR；找到同一工作就接手，全部沒有才依專案規則建立卡、loop 與分支。不得為同一工作開第二張卡、第二份 loop 或平行分支。

需求不清楚或工作太大時，先依 [需求釐清與拆票](references/intake.md) 問清楚並拆票，再建 loop。

新 loop 至少記錄目標、整體驗收、已知、來源、計畫、目前狀態與下一步；分支基準、看板、守門與合併規則以 workspace 規範為準。接手時從既有「下一步」與最近證據繼續，不重做已通過項目。

執行者負責最後決策。若指定 `--reviewer codex|claude`，在計畫定案及改動完成時請可用的另一模型做反方審查；意見只供參考，裁決順序是使用者決策、workspace 規範、直接證據。未指定或 reviewer 不可用時不阻塞主線，記錄原因即可。

長任務預設每 5 分鐘續跑一次。使用宿主提供的 recurring task／continuation；宿主沒有續跑能力時不得假裝背景執行，完成本輪後留下可直接接續的下一步。每輪必須產生新證據、完成一個可驗收切片或明確記錄阻塞；不能只重報未變狀態。

## 一次只做一張票

LOOP 計畫表的每個 step 就是一張 ticket。每輪只挑最前面一張 `READY` 且依賴已完成的票，做到驗收通過、`DONE`、checkpoint 寫入、LOOP「目前狀態」更新，才換下一張。票卡住才換別張，並在 checkpoint 記錄卡在哪、已試過什麼。不順手做計畫外的事；發現新工作就加進計畫表當新票。

## 生命週期

唯一循環：`Inspect → Plan → Execute → Validate → Review/Replan → Checkpoint`。

- Inspect：盤點現況、產物、限制與未知，不假設。
- Plan：寫目標、整體驗收、主要 step、風險、停止條件；只細拆近期一至兩步；先用最小有界檢查驗證最可能推翻方案的假設。
- Execute：每輪推進一個主要 step，走已知最短的路。
- Validate：用實際執行結果；單元測試不替代整體驗收。step 改了程式、要標 `DONE` 前，必過[簡化審查](references/simplicity-review.md)。
- Review/Replan：依新證據重排，不重做已通過的工作。
- Checkpoint：只在狀態變化或有新證據時寫。

任務狀態：`DISCOVERING`、`PLANNED`、`RUNNING`、`VALIDATING`、`REVIEWING`、`WAITING`（等具名的人或事件）、`BLOCKED`、`MONITORING`；終態 `COMPLETE`／`CANCELLED`／`SUPERSEDED`／`FAILED`，只有整體驗收通過才 `COMPLETE`。Step 狀態：`PENDING`、`READY`、`RUNNING`、`VALIDATING`、`DONE`、`BLOCKED`、`FAILED`、`CANCELLED`、`SKIPPED`、`SUPERSEDED`；未驗收不得 `DONE`。合法轉換由 schema 與寫入工具把關，不在這裡重述。

## 交付點與不停工

階段、大功能、里程碑都是交付點，列入同名 `*.delivery.json`。交付點寫 `VALIDATING` 並附全部通過的檢查時，進度工具自動送出既有授權的背景部署，AI 立即繼續無依賴工作，不反覆等待或重送。部署與線上驗收未過，不得標該交付點 `DONE` 或整體 `COMPLETE`。實作完成且品質驗證通過後，部署、提交、推送、合併沿用既有授權直接做並讀回線上版本；只有品質或合併閘門失敗、明確安全風險、會中斷進行中的工作、缺部署以外的必要授權時才暫停，並寫清阻擋證據與下一步。細則見 [交付](references/delivery-policy.md)。

## 瀏覽器跨版交付

網頁發布的驗收規則與原件格式見 [交付](references/delivery-policy.md)「瀏覽器跨版驗證」。

## 每輪三問

1. 更接近目標了嗎：對照整體驗收列本輪新證據；改檔數、工具呼叫數、局部測試數不算進度。
2. 走的是目前最佳路徑嗎：在已知、可行、已授權的路中選最直接的一條。
3. 走偏了嗎：在做無關功能、過度補文件、重複驗證，立刻停下拉回。

連續兩輪沒有新證據就換方法、縮小問題或提出決策，不重跑原命令。

原始交付決定範圍；每個旁支必須能指出不做就無法交付的原始要求，否則不阻擋主線。使用者糾正方向時先更新當前步驟，不得回答後又恢復被否定的做法。只剩背景工作時等待該工作的完成事件；重讀未變日誌、寫進度或重複回報不算進展，不觸發新一輪。

## 何時重新設計

只在有新證據時考慮：同一步連兩次失敗、發現原假設錯、要改的範圍比計畫大很多、或有明顯更短的路。不因「想更漂亮」重設計。

判斷方式：列出兩三條可行路，各自比較會動到的範圍、程式量、風險，選破壞最小、程式最少且仍達成整體驗收的一條。能沿用現有實作就不另起爐灶。

不放棄：做不下去先換方法或縮小問題，不直接停；停止只依下面「停止」三種情況。

不發散：重設計必須指出它解決哪個原始要求；同一步最多重設計一次，再失敗就回報證據。重設計新增的工作加進計畫表當新票，不塞進當前票。決定與放棄的做法，連同理由寫進 checkpoint。

## 證據

重要結論連到命令輸出、測試名、檔案路徑與版本。有驗過直接講死並附來源；沒驗過寫「未查證」；講證據同時講邊界。註解、文件、commit 訊息、他人報告描述的是意圖不是行為，引用前先驗證。結果照實報，沒跑的檢查主動講。

## 授權與不停下

不自行增加授權；不假裝通過（不放寬測試、不刪驗證、不用「完成」文字代替交付）；不改寫使用者原始資料。手上有事就不停：卡死的是必要 step 才當場停；非必要 step 卡住先做別的，最後再試一次。只是取捨就自己決定；拿不定主意就上網查最佳做法或問另一個 AI；等人只在缺授權或重大選擇。不花使用者的錢、不調機器規格。

## 停止

只有三種：整體驗收全過標 `COMPLETE`；做不到（要有「死在哪一步」的直接證據，且換過方法）；缺人類決定（只缺授權或選擇）。停止前交 [停止舉證](references/stop-policy.md)；等人時停排程、不喚醒。

## 紀錄與回報

- 一任務一份 LOOP，整檔不超過 3,000 字元（範本 [task.loop.md](templates/task.loop.md)）：目標、整體驗收、計畫表、目前狀態。歷史進 checkpoint JSONL，只准經 `~/tools/cash-rule-checkpoint` 寫入（細則 [紀錄](references/reporting.md)）。短任務不建檔。
- 對人回報只有四件事：目標一句、做法一句、每個 step 一句成果、重大事件一行。

## 本機 Essence

細則見 RULES.md 與 [派工](references/model-dispatch.md)。Rust 一個 repo 只有一份 `target/`，由 cargo 包裝程式與 guard 擋，細則見 cargo-cache 技能。shell 萬用字元由 shell_glob_guard 擋。

## 按需載入

[評估](references/evaluation-policy.md)、[派工](references/model-dispatch.md)、[停止舉證](references/stop-policy.md)、[執行與看門狗](references/runtime.md)、[交付](references/delivery-policy.md)、[背景](references/context-policy.md)、[紀錄](references/reporting.md)、[需求釐清與拆票](references/intake.md)。
