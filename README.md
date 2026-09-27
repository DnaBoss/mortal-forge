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

## AI 助手入口

本 repo 的規則來源是 `AGENTS.md`。目前同時提供薄入口給主流 coding assistant：

- Codex／支援 AGENTS 的工具：`AGENTS.md`
- Claude Code：`CLAUDE.md`
- Gemini CLI：`GEMINI.md`
- Cursor：`.cursor/rules/mortal-mcp.mdc`
- Windsurf：`.windsurf/rules/mortal-mcp.md`
- GitHub Copilot：`.github/copilot-instructions.md`

這些入口只指向同一套規則，不複製內容；更新工程標準時改 `AGENTS.md` 即可。`mortal-tools init /path/to/repo` 也會寫入同樣入口。

## 工具

- `fluke_status`：服務 PID／健康檢查／版本。
- `fluke_open_preview`：開啟 PLAY 試玩，沿用現有服務。
- `fluke_validate`：隔離 clock／sidepot／bot-ledger／full-table／ledger-restart／bot-restart 驗收。
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

已驗證：`smoke_test.py` 透過真 HTTP MCP 呼叫查狀態、探索五工具、拒絕錯誤參數及拒絕同時重複操作；詳 `smoke-result.json`。開啟與隔離測試工具本輪未經 MCP 執行，底層腳本既有驗證不算此介面的驗證。

- `fluke_audit_continuity`：兩分鐘唯讀十桌續局／帳務檢查，不替代多人玩法验收。
- 無動態工具掛載的session可用 `uv run python call.py fluke_status`，仍透過真MCP呼叫，沒有另一套命令實作。

麻將服務驗證：`call.py fluke_validate --arguments '{"scenario":"mahjong"}'`。沿用 Fluke 固定腳本，自有隔離 PostgreSQL，含日麻與德撲回歸；不重啟試玩 Gateway／Godot。

## npm 本機套件（0.1.0，尚未公開發布）

沿用本 repo；名稱 `mortal-dev-tools` 暫定，private 防止誤發布。Node >=22；MCP Python 入口需 uv，`uv run --frozen` 安裝鎖定依賴。MCP 服務仍為 127.0.0.1:18765，不含 AI 推論。

```sh
npm pack --pack-destination /tmp
npm install -g /tmp/mortal-dev-tools-0.1.0.tgz
mortal-tools install
mortal-tools doctor
mortal-tools connect
```

install 安裝穩定副本到 `~/.local/share/mortal-tools/package`，SKILL 到 `~/.agents/skills/mortal-tools`（Codex）與 `~/.claude/skills/mortal-tools`；僅追加有標記的共用規則區塊，不覆寫原規則。MORTAL_HOME 可供隔離測試；實際 AI 使用標準 home 路徑。重開 AI session 才能確認載入；npm 安裝本身不執行 postinstall、不啟服務、不修改客戶端連線。

`connect` 顯示本機 CLI 支援的 Codex／Claude 註冊命令；先核對既有同名配置再執行。不能把輸出命令稱作已完成註冊。已有 systemd 服務直接沿用；其他電腦可 `mortal-tools serve`，Fluke 入口需環境變數 MORTAL_FLUKE_ROOT。工具目錄預設 `~/tools/tools.json`，可設定 MORTAL_TOOL_CATALOG；不存在則回空清單，不能宣稱其他專案已安裝。

- `mortal-tools call mortal_catalog --arguments '{"query":"fluke"}'`：搜尋現有工具。`mortal_guide` 按 name 讀用法、限制與 SKILL；`mortal://skills/shared` 為 MCP SKILL resource。沒有 MCP adapter 的工具明列 existing_shell_only。
- `mortal-tools init /path/to/repo`／`uninit`：只新增／移除該 repo 的 AGENTS.md、CLAUDE.md、GEMINI.md、Cursor rule、Windsurf rule、Copilot instructions 專屬區塊，不影響其他內容。
- 更新：先安裝新版 npm 包，再 `mortal-tools update`；不自動上網找 latest，不自動重啟服務。
- 解除：`mortal-tools uninstall` 移除受管 SKILL／全域規則，保留穩定程式副本、服務、連線配置和專案 init 區塊，避免仍在運作的服務失效；npm 包另用 `npm uninstall -g mortal-dev-tools` 移除。
- 共用小程式未全面遷入本 repo；先保留原位置及唯一 tools.json。此次不把模型呼叫、DB 或 Windows 工具盲目封裝／執行。

實作計畫與範圍見 docs/package-plan.md。參考：npm 官方 https://docs.npmjs.com/files/package.json/；Claude 個人 SKILL https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview；Codex／Claude MCP 指令依本機 CLI --help 查證。
