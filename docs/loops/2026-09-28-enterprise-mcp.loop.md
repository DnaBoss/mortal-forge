# MORTAL MCP 企業級 LOOP

<!-- cash-rule-watchdog-status: PLANNED -->

- 目標：[GOAL](../goals/2026-09-28-enterprise-mcp.goal.md)；待辦：[TODO](../TODO.md)。
- 狀態：PLANNED。只有文件，尚未施工。交接時間 2026-09-28，來源 Fluke session（Claude Code）。
- 所有權：尚未指派；接手 session 先寫 owner 與開始時間，並確認沒有其他 AI 在本 repo 工作。
- 分支：本 repo 目前在 `main` 且工作樹乾淨；施工前開 `feat/<name>`，不直接改 `main`。
- 服務：`mortal-mcp.service` 正在跑 Python 版，Fluke session 會用到；切換或重啟前先確認沒有進行中的 Fluke 驗收。

## Step

| Step | 內容 | 驗收 | 狀態 |
| --- | --- | --- | --- |
| M0 | 盤點、ADR、修 catalog 提示 | ADR 寫入；catalog 測試有結果時不附空提示 | READY |
| M1 | 通用執行器、參數驗證、資源鎖、權限、稽核 | 注入／越界路徑／佔鎖／dangerous 各一個會紅的測試 | PENDING |
| M2 | 背景工作 | start→status→cancel 實跑；重啟後查得到結果 | PENDING |
| M3 | 精簡回傳 | 回傳大小上限測試；完整日誌路徑可開 | PENDING |
| M4 | Fluke 抽出的 5 個新工具＋既有 shell 工具接 MCP | 每工具成功例＋失敗例；fluke_bot_soak 實跑一次 | PENDING |
| M5 | 遷移、doctor、上線 | 9 個舊功能對照一致；systemd 切換與回退實測 | PENDING |

## 下一步

M0：讀 `server.py`、`src/`、`docs/package-plan.md`，決定 Rust 或 Python，寫 ADR。
