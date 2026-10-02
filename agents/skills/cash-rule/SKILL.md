---
name: cash-rule
description: 以證據推進跨專案工作；接手任務、ticket 或 LOOP，直到整體驗收或明確終止。
---

# cash-rule：共用執行協定

Protocol version: `1.2.0`. 使用者當前指示、既有授權與專案規則優先；本協定不增加寫入、部署、合併或外部操作授權。

## 唯一生命週期與狀態定義

唯一循環：`Inspect → Plan → Execute → Validate → Review/Replan → Checkpoint`。本節是狀態、轉換與完成條件的唯一來源；其他技能、規範與 LOOP 只引用本節，不重述流程。

Task 狀態：

- `DISCOVERING`：盤點現況、owner、產物、限制與未知。
- `PLANNED`：目標、主要 step、驗收、風險與停止條件已明確。
- `RUNNING`、`VALIDATING`、`REVIEWING`：執行、查證、審查或依證據重排。
- `WAITING`：等待具名的人、事件或外部條件；可做的獨立工作仍繼續。
- `BLOCKED`：沒有安全且已授權的下一步，需條件改變或使用者決定。
- `MONITORING`：依明確 owner、喚醒方式、鎖與停止條件持續觀察。
- 終止狀態：`COMPLETE`、`CANCELLED`、`SUPERSEDED`、`FAILED`。取消由使用者或授權者要求；被新目標取代時標 `SUPERSEDED`；只有整體驗收通過才標 `COMPLETE`。

Step 狀態：`PENDING`、`READY`、`RUNNING`、`VALIDATING`、`DONE`、`BLOCKED`、`FAILED`、`CANCELLED`、`SKIPPED`、`SUPERSEDED`。只有依賴已滿足才能 `READY`；未驗收不得標 `DONE`。LOOP 投影見 [工程政策](references/engineering-policy.md)。

合法主流程是 `DISCOVERING → PLANNED → RUNNING → VALIDATING → REVIEWING`，之後回到 `RUNNING`／`PLANNED`，或進入 `WAITING`、`BLOCKED`、`MONITORING`、終止狀態。`WAITING`／`BLOCKED`／`MONITORING` 在條件改變後可回到適當的非終止狀態。`COMPLETE`、`CANCELLED`、`SUPERSEDED`、`FAILED` 是終止狀態，不可自行恢復；新任務以 `superseded_by`／`supersedes` 欄位記錄取代關係。Step 依序 `PENDING → READY → RUNNING → VALIDATING → DONE`；驗證失敗可回 `RUNNING`。非終止 step 可進 `BLOCKED`／`FAILED`／`CANCELLED`／`SUPERSEDED`，`PENDING`／`READY`／`BLOCKED` 可依明確範圍決定 `SKIPPED`；`DONE`、`FAILED`、`CANCELLED`、`SKIPPED`、`SUPERSEDED` 為終止狀態，`BLOCKED` 可在解除後依證據回到適當的非終止狀態。

## 本機 Essence：本機 AI 執行（使用者 2026-09-28 定）

只在主機 Essence 上適用。這台電腦上的所有 repo 都要遵守，包括 ICO、DnaBoss、private 和 newretail；同一個 repo 在別台電腦不適用。

- 所有工作由監督者拆解後，派給本機 AI 執行，監督者負責驗收。可以自由安裝、使用本機模型。
- CPU 和記憶體不可用到 100%，要保留餘裕；不得繞過記憶體保護和服務上限。
- 同樣的錯不得再犯：開工先讀 `~/.agents/lessons.md`，新的錯誤要追加進去。
- 可重複使用的程式、Shell、Script，一律做成 SKILL＋MCP，放在 `~/work_space/private/mortal-mcp`。

細則唯一見 [派工規則](references/model-dispatch.md) 第一節。

## 每輪執行

依上述循環推進；每輪只推進一個主要 step。連續兩輪沒有新證據或可驗收進展，換方法、縮小問題或提出決策，不重跑原命令。首次 checkpoint 在盤點或規劃完成時寫入（`DISCOVERING`／`PLANNED`）；step 首次為 `PENDING`／`READY`。之後在每輪結束寫入；若輪內跨越必要狀態，於狀態邊界補 checkpoint，不得省略驗證階段。`iteration` 是每 task 的 checkpoint 序號，不是模型呼叫數。已終止 step 可重複投影原狀態，不可重新啟動。多輪／持續任務追加符合 [checkpoint schema](schemas/checkpoint.schema.json) 的 JSONL 紀錄，只准經 `~/tools/cash-rule-checkpoint` 寫入（見 [回報規則](references/reporting.md)）；LOOP 只保留目前狀態摘要。短任務不需為形式建立 LOOP 或 JSONL。

## 證據與停止

每項重要結論連到可觀察證據及來源、時間或版本。優先引用 Git SHA、路徑、符號／測試名稱或命令與輸出；行號可作輔助，不是唯一定位方式。模型意見、舊證據和推論清楚標示。

整體 step 完成後仍須做整合驗收。停止時明確標示 `COMPLETE`、`WAITING`、`BLOCKED`、`MONITORING` 或終止原因；LOOP 本身不是背景執行器。看門狗與鎖依 [執行與看門狗](references/runtime.md)；評估依 [評估規則](references/evaluation-policy.md)；派工依 [派工規則](references/model-dispatch.md)；checkpoint、通知與用量依 [回報規則](references/reporting.md)。

## 按需載入

- 任務背景與交接：[背景與證據](references/context-policy.md)
- 專案計畫、驗收、授權與 LOOP 投影：[工程政策](references/engineering-policy.md)
- 研究、成效或高風險比較：[評估規則](references/evaluation-policy.md)
- 模型選擇：[派工規則](references/model-dispatch.md)
- 長時工作與 watchdog：[執行與看門狗](references/runtime.md)
- 使用量與通知：[回報規則](references/reporting.md)
- LOOP 範本：[主 LOOP](templates/task.loop.md)、[step LOOP](templates/step.loop.md)
