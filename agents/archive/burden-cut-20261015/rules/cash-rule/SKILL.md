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

每輪結束，在寫checkpoint與決定下一步前，必須檢視下列三項（使用者2026-10-09定）：

- **是否更接近目標**：對照主LOOP的整體成果與驗收，列出本輪新增的可觀察證據，判斷前進、未前進或倒退；不以改檔數、文件數、工具呼叫或局部測試數代替整體進度。
- **是否使用目前最佳路徑**：比較目前已知、可行且已授權的路徑，依整體驗收、依賴、風險、成本與返工選擇最直接的一條；保留或切換都要有理由，不為證明全域最佳而無限搜尋或重做已通過的工作。
- **是否走偏並立即拉回**：檢查本輪及下一步是否仍服務整體目標。若在做無關功能、過度補文件、重複驗證或停在不屬於agent的人工成果驗收，立即停止偏離工作、重排下一個對應整體驗收的動作；不等兩輪無進展才修正。以既有checkpoint結果摘要與next記證據、路徑判斷及拉回動作，更新LOOP投影，不新增schema欄位、授權或喚醒。

依上述循環推進；每輪只推進一個主要 step。每輪動手前先指出這一步對應主 LOOP 哪一條整體驗收，寫進 checkpoint 的 `acceptance`（一個編號即可，不另寫說明）；對不上的事不做，只記待辦。有多條路時走已知最短的一條（使用者 2026-10-05 定）。連續兩輪沒有新證據或可驗收進展，換方法、縮小問題或提出決策，不重跑原命令。首次 checkpoint 在盤點或規劃完成時寫入（`DISCOVERING`／`PLANNED`）；step 首次為 `PENDING`／`READY`。之後在每輪結束寫入；若輪內跨越必要狀態，於狀態邊界補 checkpoint，不得省略驗證階段。`iteration` 是每 task 的 checkpoint 序號，不是模型呼叫數。已終止 step 可重複投影原狀態，不可重新啟動。多輪／持續任務追加符合 [checkpoint schema](schemas/checkpoint.schema.json) 的 JSONL 紀錄，只准經 `~/tools/cash-rule-checkpoint` 寫入（見 [回報規則](references/reporting.md)）；LOOP 只保留目前狀態摘要。短任務不需為形式建立 LOOP 或 JSONL。

## 證據與停止

每項重要結論連到可觀察證據及來源、時間或版本。優先引用 Git SHA、路徑、符號／測試名稱或命令與輸出；行號可作輔助，不是唯一定位方式。模型意見、舊證據和推論清楚標示。

做好且通過必要驗證的交付單位，立即在既有授權內交付可用版本，不等整個目標結束。須有同版本實際入口／部署讀回，或具體未授權、暫停、唯讀、失敗原因；不要求每輪正式部署、不以完成文字取代交付。細則與Stop收據格式見 [可用版本交付](references/delivery-policy.md)。

整體 step 完成後仍須做整合驗收。停止時明確標示 `COMPLETE`、`WAITING`、`BLOCKED`、`MONITORING` 或終止原因；LOOP 本身不是背景執行器。看門狗與鎖依 [執行與看門狗](references/runtime.md)；評估依 [評估規則](references/evaluation-policy.md)；派工依 [派工規則](references/model-dispatch.md)；checkpoint、通知與用量依 [回報規則](references/reporting.md)。

## 不因單一問題停下（使用者 2026-10-03 定）

- 手上還有能做的事，就不因任何一個或多個問題停下來。只有「沒有人類決定，後面一件事都做不了」才停。
- 卡死的是必要 step（它對應的整體驗收沒有其他 step 或其他路能滿足）：當場停，不再做其他 step（使用者 2026-10-05 定）。
- 卡死的是非必要 step（驗證失敗且修不好，或連續兩輪沒有新進展、換方法也無解）：不併回，寫進進度文件並回報，繼續做 LOOP 裡其他能做的 step。其他都做完後回來再修一次，還不行才停。
- 真正的停止只有三種：整體驗收全過；必要 step 卡死；非必要 step 卡死且已無其他事可做。後兩種停止前必須交齊 [停止舉證](references/stop-policy.md)，交不出來就繼續做。
- 需要回報但不需要同意的事，回報後繼續做，不等回覆。
- 不調整機器規格、不花使用者的錢，除非使用者明確同意。這一條不因本節放寬。

## Rust 編譯產物（使用者 2026-10-03 定，強制）

- 一個 repo 不論開多少工作樹或 workspace，都只能有一份 `target/`（使用者 2026-10-04 重申）；新工作樹與每次編譯前必須確認共用位置，不得另建整份快取或指定獨立 `CARGO_TARGET_DIR`。
- 本機 Essence 的 `~/.local/bin/cargo` 是共用 target 包裝程式（`~/tools/cargo_shared_target.py`），終端機、IDE、rust-analyzer 與所有 AI 的 cargo 都經過它；一律用 PATH 上的 `cargo`，不得改呼叫 `~/.cargo/bin/cargo` 或設 `CARGO_ALLOW_SEPARATE_TARGET=1` 繞過，除非使用者明確同意。
- 收工前盤點實體副本、容量、程序使用狀態與略過原因；已授權清理的閒置重複產物必須清除，不可只寫待辦。來源碼、模型、資料與使用中的執行檔不得刪除；查不清就保留並記錄。
- `PreToolUse` 攔獨立編譯位置，`Stop` 核對新副本，`SessionEnd` 寫快速紀錄；經 repo 明確啟用後，由有鎖、有時限、無自動重試的背景工作清理已登記的略過項目。
- 保留快取所在工作樹不得直接移除；先搬移快取並更新登記及連結。
- 工具、授權、程序檢查與證據位置唯一見 [cargo-cache 技能](../../../skills/cargo-cache/SKILL.md)。

## 按需載入

- 任務背景與交接：[背景與證據](references/context-policy.md)
- 專案計畫、驗收、授權與 LOOP 投影：[工程政策](references/engineering-policy.md)
- 研究、成效或高風險比較：[評估規則](references/evaluation-policy.md)
- 模型選擇：[派工規則](references/model-dispatch.md)
- 準備停止（不知道路、做不到、缺人類決定）：[停止舉證](references/stop-policy.md)
- 長時工作與 watchdog：[執行與看門狗](references/runtime.md)
- 使用量與通知：[回報規則](references/reporting.md)
- LOOP 範本：[主 LOOP](templates/task.loop.md)、[step LOOP](templates/step.loop.md)
