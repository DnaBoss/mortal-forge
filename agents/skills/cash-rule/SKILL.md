---
name: cash-rule
description: 以證據推進長任務：生命週期、整體驗收、停止條件；接手任務直到整體驗收或明確終止。
---

# cash-rule：執行協定（2026-10-15 精簡版）

Protocol version: `1.2.0`. 使用者當前指示與專案規則優先；本協定不增加任何授權。原文封存於 `../../archive/burden-cut-20261015/rules/cash-rule/`。

## 生命週期

唯一循環：`Inspect → Plan → Execute → Validate → Review/Replan → Checkpoint`。

- Inspect：盤點現況、產物、限制與未知，不假設。
- Plan：寫目標、整體驗收、主要 step、風險、停止條件；只細拆近期一至兩步。
- Execute：每輪推進一個主要 step，走已知最短的路（使用者 2026-10-05 定）。
- Validate：用實際執行結果；單元測試不替代整體驗收。
- Review/Replan：依新證據重排，不重做已通過的工作。
- Checkpoint：只在狀態變化或有新證據時寫（使用者 2026-10-15 定）。

任務狀態：`DISCOVERING`、`PLANNED`、`RUNNING`、`VALIDATING`、`REVIEWING`、`WAITING`（等具名的人或事件）、`BLOCKED`、`MONITORING`；終態 `COMPLETE`／`CANCELLED`／`SUPERSEDED`／`FAILED`，只有整體驗收通過才 `COMPLETE`。Step 狀態：`PENDING`、`READY`、`RUNNING`、`VALIDATING`、`DONE`、`BLOCKED`、`FAILED`、`CANCELLED`、`SKIPPED`、`SUPERSEDED`；未驗收不得 `DONE`。合法轉換由 schema 與寫入工具把關，不在這裡重述。

## 每輪三問（使用者 2026-10-09 定）

1. 更接近目標了嗎：對照整體驗收列本輪新證據；改檔數、工具呼叫數、局部測試數不算進度。
2. 走的是目前最佳路徑嗎：在已知、可行、已授權的路中選最直接的一條。
3. 走偏了嗎：在做無關功能、過度補文件、重複驗證，立刻停下拉回。

連續兩輪沒有新證據就換方法、縮小問題或提出決策，不重跑原命令。

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

## 按需載入

[工程政策](references/engineering-policy.md)、[評估](references/evaluation-policy.md)、[派工](references/model-dispatch.md)、[停止舉證](references/stop-policy.md)、[執行與看門狗](references/runtime.md)、[交付](references/delivery-policy.md)、[背景](references/context-policy.md)、[紀錄](references/reporting.md)。
