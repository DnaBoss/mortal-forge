---
name: mortal-mcp
description: 使用 CASH 本機 MCP 服務查詢及操作專案工具；目前提供 Fluke 試玩狀態、開啟與隔離驗收，避免重寫常用指令。
---

服務：`http://127.0.0.1:18765/mcp`，systemd user unit `mortal-mcp.service`。
先查 `fluke_status`；health 成功不代表遊戲能玩。`fluke_open_preview` 只開試玩，不升級既有 Gateway。
`fluke_validate` 的 scenario 為 clock、sidepot、bot-ledger、full-table；只處理自有 PLAY 測試 DB，不以局部結果宣稱全產品通過。
`fluke_restart_preview` 尚待 Ledger revision 重啟驗證，現在回傳拒絕，不可绕過清 DB。使用者已授權本次遊戲換版，修正後不需重問。

工具底層沿用 MORTAL_FLUKE_ROOT 指定 repo 的既有 scripts，禁止複製另一套業務邏輯。
忙碌或失敗先查 log／實際程序，不自動重試、不直接另開一份相同任務。
輸出只讀摘要；失敗或核對證據時才讀詳細 log。工具不呼叫模型；Godot 渲染中不可啟動本機推論。
新增其他專案工具沿用同一服務，固定參數與命令，不提供任意 shell／SQL 執行入口。
安裝設定見 repo README；寫好設定不等於當前 AI session 已載入工具。
