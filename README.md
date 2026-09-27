# MORTAL MCP

MORTAL 專用本機工具服務。入口：`http://127.0.0.1:18765/mcp`。
獨立 repo，沒有 Git remote；只在本機運行，不對外發布。

## 執行

```sh
uv sync --frozen
MORTAL_FLUKE_ROOT=/absolute/Fluke/checkout uv run --frozen python server.py
```

客戶端採 Streamable HTTP：

```json
{"mcpServers":{"mortal":{"type":"http","url":"http://127.0.0.1:18765/mcp"}}}
```

不同 AI 客戶端設定格式可能不同；本範例不代表已替所有客戶端安裝。

## 工具

- `fluke_status`：服務 PID／健康檢查／版本。
- `fluke_open_preview`：開啟 PLAY 試玩，沿用現有服務。
- `fluke_validate`：隔離 clock／sidepot／bot-ledger／full-table 驗收。
- `fluke_restart_preview`：已接回：授權後備份、退款已入帳桌上籌碼、保留歷史並換版；未完成手牌取消。

Skill 位於 `.agents/skills/mortal-mcp/SKILL.md`。工具只包裝 Fluke 腳本；服務本身不呼叫 AI。
同時操作會拒絕後來的請求，回傳完整 log 路徑及最多 1800 bytes 摘要。
MCP 層的 lock 不涵蓋人手直接執行原腳本；不要同時繞過入口執行。
逾時先中斷並等待清理，若仍卡住會停止該命令；需查殘留測試資源，不自動重試。

## 本機服務

`systemctl --user status mortal-mcp.service`

`journalctl --user -u mortal-mcp.service -n 30 --no-pager`

服務由使用者 systemd 管理，不建立 cron。停止服務不代表遊戲停止。
SDK 使用官方 Python MCP SDK，固定版本於 `uv.lock`。

安裝本機服務：`bash scripts/install-service.sh /absolute/Fluke/checkout`。已在執行的服務不會被安裝腳本重啟。

已驗證：`smoke_test.py` 透過真 HTTP MCP 呼叫查狀態、探索四工具、拒絕錯誤參數及拒絕同時重複操作；詳 `smoke-result.json`。開啟與隔離測試工具本輪未經 MCP 執行，底層腳本既有驗證不算此介面的驗證。
