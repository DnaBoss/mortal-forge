# MORTAL MCP

MORTAL 是可安裝的標準 Skill／Plugin 套件與本機 MCP 服務。Skill 負責工作流，底層呼叫本 repo 提供的 Rust MCP 服務、固定 CLI、Shell adapter 或其他 MCP tool。

主要目標：

- `skills/` 提供標準可安裝 Skill。
- `plugin.json` 與 `mcp.json` 提供 Plugin/MCP 打包資訊。
- Rust 服務預設在 `127.0.0.1:18765` 提供 `/health` 與 `/mcp`。
- 服務可透過 `MORTAL_CONFIG` 支援一間或多間公司，每家公司工具以固定 adapter 登記。
- 不提供任意 shell、SQL、刪檔、遠端主機、憑證、付款或正式環境萬用入口。

舊 Python MCP adapter 仍保留作為過渡 fallback；新開發以 Rust service 為準。

## 執行

```sh
cargo run --bin mortal-mcp
```

客戶端採 Streamable HTTP：

```json
{"mcpServers":{"mortal":{"type":"http","url":"http://127.0.0.1:18765/mcp"}}}
```

不同 AI 客戶端設定格式可能不同；本範例不代表已替所有客戶端安裝。

多公司設定範例：

```sh
MORTAL_CONFIG=config/mortal.example.json cargo run --bin mortal-mcp
```

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

標準 Skill 位於 `skills/`。`.agents/skills/` 只保留給本 repo 內會掃描該路徑的 agent 作相容入口。
同時操作會拒絕後來的請求，回傳完整 log 路徑及最多 1800 bytes 摘要。
MCP 層的 lock 不涵蓋人手直接執行原腳本；不要同時繞過入口執行。
逾時先中斷並等待清理，若仍卡住會停止該命令；需查殘留測試資源，不自動重試。

## 本機服務

`systemctl --user status mortal-mcp.service`

`journalctl --user -u mortal-mcp.service -n 30 --no-pager`

服務由使用者 systemd 管理，不建立 cron。停止服務不代表遊戲停止。
SDK 使用官方 Python MCP SDK，固定版本於 `uv.lock`。
Rust MCP 使用 `rmcp` 與 `rmcp-actix-web`。

安裝本機服務：`bash scripts/install-service.sh /absolute/Fluke/checkout`。已在執行的服務不會被安裝腳本重啟。

已驗證：`smoke_test.py` 透過真 HTTP MCP 呼叫查狀態、探索五工具、拒絕錯誤參數及拒絕同時重複操作；詳 `smoke-result.json`。開啟與隔離測試工具本輪未經 MCP 執行，底層腳本既有驗證不算此介面的驗證。

- `orca_claude_env_check`／`orca_stop_stale_daemon`：ORCA 裡 Claude Code 報「模型不存在」時使用。先唯讀查出帶著過期 `ANTHROPIC_BASE_URL` 的 ORCA 背景程式；使用者授權後才關閉它（會關掉該背景程式內所有 Claude 對話，先存 resume 清單）。流程見 `skills/orca-claude-env/SKILL.md`，底層工具在 `~/tools/orca_claude_env/`。
- `localai_dispatch`：在主機 Essence 把工作派給本地模型（code／review／second），回答只當線索要再驗證；檔案路徑限定在家目錄。流程見 `skills/local-ai/SKILL.md`。
- `remote_zip_list`／`remote_zip_extract`：只下載遠端 https 大壓縮檔裡需要的檔案（例如 Godot 輸出模板），輸出目錄限定在家目錄。
- `fluke_audit_continuity`：兩分鐘唯讀十桌續局／帳務檢查，不替代多人玩法验收。
- 無動態工具掛載的session可用 `uv run python call.py fluke_status`，仍透過真MCP呼叫，沒有另一套命令實作。

麻將服務驗證：`call.py fluke_validate --arguments '{"scenario":"mahjong"}'`。沿用 Fluke 固定腳本，自有隔離 PostgreSQL，含日麻與德撲回歸；不重啟試玩 Gateway／Godot。

## npm 本機套件（0.2.0 方向，尚未公開發布）

沿用本 repo；名稱 `mortal-dev-tools` 暫定，private 防止誤發布。Node >=22；服務底層是 Rust，legacy Python 入口只作 fallback。MCP 服務仍為 127.0.0.1:18765，不含 AI 推論。

```sh
npm pack --pack-destination /tmp
npm install -g /tmp/mortal-dev-tools-0.1.0.tgz
mortal-tools install
mortal-tools doctor
mortal-tools connect
```

install 安裝穩定副本到 `~/.local/share/mortal-tools/package`，標準 Skill 來源在套件內 `skills/`，並安裝 `mortal-tools` skill 到 `~/.agents/skills/mortal-tools`（Codex）與 `~/.claude/skills/mortal-tools`；僅追加有標記的共用規則區塊，不覆寫原規則。MORTAL_HOME 可供隔離測試；實際 AI 使用標準 home 路徑。重開 AI session 才能確認載入；npm 安裝本身不執行 postinstall、不啟服務、不修改客戶端連線。

`connect` 顯示本機 CLI 支援的 Codex／Claude 註冊命令；先核對既有同名配置再執行。不能把輸出命令稱作已完成註冊。已有 systemd 服務直接沿用；其他電腦可 `mortal-tools serve`，Fluke 入口需環境變數 MORTAL_FLUKE_ROOT。工具目錄預設 `~/tools/tools.json`，可設定 MORTAL_TOOL_CATALOG；不存在則回空清單，不能宣稱其他專案已安裝。

- `mortal-tools call mortal_catalog --arguments '{"query":"fluke"}'`：搜尋現有工具。`mortal_guide` 按 name 讀用法、限制與 SKILL；`mortal://skills/shared` 為 MCP SKILL resource。沒有 MCP adapter 的工具明列 existing_shell_only。
- `mortal-tools init /path/to/repo`／`uninit`：只新增／移除該 repo 的 AGENTS.md、CLAUDE.md、GEMINI.md、Cursor rule、Windsurf rule、Copilot instructions 專屬區塊，不影響其他內容。
- 更新：先安裝新版 npm 包，再 `mortal-tools update`；不自動上網找 latest，不自動重啟服務。
- 解除：`mortal-tools uninstall` 移除受管 SKILL／全域規則，保留穩定程式副本、服務、連線配置和專案 init 區塊，避免仍在運作的服務失效；npm 包另用 `npm uninstall -g mortal-dev-tools` 移除。
- 共用小程式未全面遷入本 repo；先保留原位置及唯一 tools.json。此次不把模型呼叫、DB 或 Windows 工具盲目封裝／執行。

實作計畫與範圍見 docs/package-plan.md。參考：npm 官方 https://docs.npmjs.com/files/package.json/；Claude 個人 SKILL https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview；Codex／Claude MCP 指令依本機 CLI --help 查證。

## 共用規則與工具清單（2026-09-29 起納入本 repo）

- `agents/`：跨 AI 共用規則（cash-rule、白話輸出、本機模型管理、錯誤知識庫 `lessons.md`）。本機 `~/.agents` 是指向這裡的連結。
- `tools/`：可重用小工具與工具清單 `tools.json`。本機 `~/tools` 是指向這裡的連結。
- 不進 Git：公司專案衍生的研究資料（`tools/cash_rule_study`、`tools/cash_rule_pilot`）、同步來的技能、備份、執行紀錄。規則見 `.gitignore`。
