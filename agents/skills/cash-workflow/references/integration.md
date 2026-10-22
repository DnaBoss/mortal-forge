# 每輪技能接入

本模組把既有規則整理成操作順序，不取代 `~/.agents/RULES.md`、白話檢查、工程守門與專案規則。原規則保持唯一來源；沒有把全文搬進每輪訊息，避免反覆增加無關內容。

| 項目 | 何時讀／執行 |
| --- | --- |
| `../SKILL.md` | 每次使用者訊息與新工作階段；依前文判斷任務類型 |
| `../scripts/turn_context.py` | 宿主呼叫掛勾時輸出技能本文，不分析或保存提示內容 |
| `../scripts/test_turn_context.py` | 修改載入方式後執行；包含缺檔、空檔及非法輸入對照 |
| `~/.agents/RULES.md` | 工程與其他詳細規則的權威來源 |

Codex 的 `~/.codex/hooks.json` 與 Claude Code 的 `~/.claude/settings.json` 各增加 `SessionStart`、`UserPromptSubmit` command hook，命令為 `/usr/bin/python3 /home/cash/.agents/skills/cash-workflow/scripts/turn_context.py`，逾時 5 秒。只新增此技能的項目，保留既有掛勾與權限。技能在兩端以連結共用一份。

每次使用者訊息都輸出，不以「已讀過」跳過。工具呼叫間的模型內部步驟不重複注入。壓縮若觸發 SessionStart 會重送，否則下一次 UserPromptSubmit 重送。未支援這兩事件的宿主只能依全域規則入口套用，不能宣稱每輪自動載入。

掛勾採既有 `hookSpecificOutput.additionalContext` 格式。程式測試只證明輸出，設定核對只證明接線；新 Codex、Claude Code／Orca 工作階段是否實際接收須另驗，不能用模型自稱遵守當成證據。分類由模型讀上下文決定，程式不會用「修」「開」等字眼硬分任務。

復原時先比較安裝前備份與現況，只移除本技能新增的兩個事件項目及技能連結；若後續有其他修改，不直接整份覆蓋設定。既有安全與白話掛勾不可停用。

此技能不提供 MCP 呼叫：每輪上下文屬宿主掛勾，加入網路服務只會增加依賴。已登記到共用工具清單；不呼叫模型、不連網、不寫對話或憑證。

精簡實作的按需工具、版本、限制與使用方式見 [精簡實作檢查](code-quality.md)。只在相應任務讀取，不將全文每輪注入。
