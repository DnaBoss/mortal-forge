## 跨專案工作共用章法

@/home/cash/.agents/context-evaluation-workflow.md

## 共用工程章法（cash 2026-09-12）

非瑣碎任務在動作前，完整讀取並遵守 `/home/cash/.agents/skills/cash-rule/references/engineering-policy.md`。
第一個可執行動作記時間戳並查用量來源；先評估方法、規劃全貌，再細拆近期步驟。一般工作用共用 start-work，持續多步工作再讀共用 cash-rule，不需使用者逐次提醒。
簡單問答不強制 LOOP／排程，評估或診斷不自行實作。本規範不增加合併、部署或外部操作授權，專案規則與當前使用者指示優先。

## 白話輸出：每次回答強制適用（cash 2026-09-11）

所有專案與每次回答都用繁體中文白話，先講結果。新對話、續接、換模型後仍適用。
常用慣用語保留，例如「學習曲線」。陌生術語不能因為是專有名詞就直接丟給使用者。
TCN 先說「能讀連續走勢的模型」；驗證窗說「拿來測試的那段日期」；凍結模型說
「訓練完成後固定版本，測試期間不再修改」。必要原名須在同一句附白話解釋。
程式碼、命令與引用維持正確，外面的解釋仍用白話。不因技術任務而自動停用。
每次送出前檢查陌生用語與冗詞，有就重寫。完整規則：`/home/cash/.agents/plain-output/POLICY.md`。
不得為讓自己的回答過關而停用或改動檢查程式。使用者明確要求原文或技術細節時保留必要原名。

## DB／遠端操作

禁止無界逐筆呼叫與模型驅動重試。使用有明確筆數／時間上限的批次；能用交易就用交易，能冪等就用冪等鍵。分段需有每批上限、停止條件、續跑位置及部分失敗／復原紀錄。外部失敗後先查狀態，不盲目重送。完整規則唯一見 `/home/cash/.agents/skills/cash-rule/references/engineering-policy.md`。

## 資料去重與完整性：禁止只看主鍵或唯一鍵（cash 2026-08-19 定）

任何資料去重、回測資料可用性或「資料完整」結論，**不得只以主鍵、唯一索引或 `ON CONFLICT` 作為證據**。必須同時完成並報告：

- 以事件內容定義去重鍵；tick 不得只用時間，須納入能識別同一事件的價格、量與必要合約／報價內容。
- 核對去重前筆數、刪除筆數、去重後筆數，三者必須相符；每張被處理表都要列出結果。
- 依該市場實際交易時段驗證時間線：分鐘／日／月資料比較預期與實際 bar 數並列出缺口；tick 檢查交易時段內的分鐘覆蓋與異常空窗，不把休市或正常無成交誤判為缺漏。
- 只有「內容重複為零」且「無未解釋時間缺口」才可宣稱資料可用；來源優先序與保留規則必須可追溯。

<!-- CODEGRAPH_START -->
## CodeGraph

In repositories indexed by CodeGraph (a `.codegraph/` directory exists at the repo root), reach for it BEFORE grep/find or reading files when you need to understand or locate code:

- **MCP tool** (when available): `codegraph_explore` answers most code questions in one call — the relevant symbols' verbatim source plus the call paths between them, including dynamic-dispatch hops grep can't follow. Name a file or symbol in the query to read its current line-numbered source. If it's listed but deferred, load it by name via tool search.
- **Shell** (always works): `codegraph explore "<symbol names or question>"` prints the same output.

If there is no `.codegraph/` directory, skip CodeGraph entirely — indexing is the user's decision.
<!-- CODEGRAPH_END -->
<!-- mortal-tools:start -->
共用工具：先讀 ~/.agents/skills/mortal-tools/SKILL.md；搜尋既有工具後再實作。簡單讀檔／搜尋直接 Shell，重複流程復用腳本，已有 MCP 操作依 SKILL 呼叫。不得重造已有工具；授權、模型成本與專案規則仍優先。
<!-- mortal-tools:end -->
