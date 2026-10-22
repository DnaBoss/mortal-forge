# 跨專案 AI 共用規範

適用 Codex、Claude Code 與其他讀取本文件的 AI，跨專案、session、worktree 與模型。使用者當前指示及專案規則優先。非瑣碎工程工作的唯一生命週期與狀態定義在 `/home/cash/.agents/skills/cash-rule/SKILL.md`；各技能、工程規範、入口描述與 LOOP 不另寫一套。若外掛快取與這份共用規範或 canonical cash-rule 衝突，按 canonical 定義執行，並記錄快取不同步。

## 已移除技能（使用者2026-10-04定）

- `brainstorming`／`superpowers:brainstorming` 已移除。不得重新載入、安裝或由其他技能轉交至它；外掛更新後若再次出現，也不使用。既有任務授權不因設計、規格或計畫缺少額外批准而失效；合併、正式部署、增加費用等原授權邊界照舊。

## 背景與評估

- 只載入當前 step 必要背景：目標、現況、可觀察證據、未知、限制、允許動作、完成條件與必要路徑。交接不得把前一個 AI 的說法當證據。
- 分清當下可見資料、事後資訊與尚未取得的資料；縮小無關上下文，但保留會改變判斷的限制、失敗案例與驗收條件。
- 影響成果、資料、金額、權限或正式驗收時，依 [評估規則](/home/cash/.agents/skills/cash-rule/references/evaluation-policy.md) 固定指標、對照、門檻、樣本及停止條件。其他文件只引用該規則。

## 派工

在主機 Essence 上，所有工作派給本機 AI 執行、錯誤寫入 `~/.agents/lessons.md` 且開工先讀、可重用程式做成 mortal-mcp 的 SKILL＋MCP；細則見下列派工規則第一節。

模型選擇和用量紀錄唯一依據是 `/home/cash/.agents/skills/cash-rule/references/model-dispatch.md` 與 `/home/cash/.agents/skills/cash-rule/references/reporting.md`。依預期總成本、能力、風險、隱私與返工可能選擇執行者；Essence 以外不預設本機優先，也不把本機輸入字元直接算成節省的雲端 token。

## 架構與流程的視覺呈現（使用者 2026-10-12 定）

解說或製作文件涉及層級、包含關係、呼叫方向、資料流、步驟或循環，且圖能提升理解時，使用 [architecture-diagrams 技能](skills/architecture-diagrams/SKILL.md)。不要求使用者先說出專有名詞。用真正的架構圖／流程圖表達關係，不把長段文字、表格或文字加箭頭當成已完成視覺化；簡單問答與純對照資料不強制畫圖。技能內附使用者認可的參考圖。

## 工具與程式理解

- 大量搜尋與重複性工作先程式化；先查 `~/tools/README.md` 和 `~/tools/tools.json`，優先重用現有工具。
- 避免用完即丟的一次性程式。先判斷將來是否可能重用；凡有合理重用機會，就整理成短小、用途單一的工具放進 `~/tools/` 並登記清單。能用純函式表達的邏輯優先用純函式；必要的檔案、資料庫或網路操作集中在明確入口，記錄副作用與風險。只適用單一專案的程式留在該 repo，並登記位置，不另複製。
- 新增／修改可重用程式時更新清單，記用途、位置、呼叫範例、輸入／輸出、依賴、讀寫與風險、驗證方式。秘密不得放入清單。小樣本和失敗案例先驗證，再擴大使用。
- 不因自動化增加授權。DB／遠端操作遵守 `/home/cash/.agents/skills/cash-rule/references/engineering-policy.md` 的有界批次、交易、冪等、部分失敗與復原規則；不做無界逐筆呼叫或模型驅動重試。
- 若 repo 有 `.codegraph/`，理解程式前先用 `codegraph`；沒有索引才用 `rg`、讀檔或其他方式。Rust 程式優先使用 `rust-analyzer`。
- 使用前先檢查工具是否已安裝及版本；可用就直接使用。安裝若需 sudo、帳號、白名單、付費或人工確認，先完成其他可做工作，再清楚回報卡點；不可反覆重試或假稱已安裝。

交接與多輪歷史使用 cash-rule 的 checkpoint schema。非工程或不需要持續追蹤的短任務，不為格式建立額外檔案。
