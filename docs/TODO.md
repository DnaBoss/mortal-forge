# TODO：MORTAL MCP 企業級

依序做；每項完成要附測試或實跑證據。目標與完成條件見 [GOAL](goals/2026-09-28-enterprise-mcp.goal.md)。

## M0 盤點與決策

- [ ] 決定新執行器用 Rust（`src/`，既有 package-plan 方向）或先強化 Python；寫 ADR（為什麼、放棄什麼）。
- [ ] 修 `mortal_catalog` 永遠附「Empty catalog」提示（`server.py:82`），有結果時不附。
- [ ] 列出 `~/tools/tools.json` 25 個工具，標出哪些值得接 MCP、哪些維持 shell。

## M1 核心執行器

- [ ] config schema：`name / purpose / argv 模板 / params schema / cwd 規則 / level(read_only|mutation|dangerous) / timeout / resources[] / summary 規則`。
- [ ] 參數驗證：型別、列舉、長度、路徑必須在允許根目錄內；拒絕 shell metacharacter 注入（argv 陣列執行，不經 shell）。
- [ ] 資源鎖：依 `resources[]` 各自上鎖；拿不到回 `busy` 與持有者 job_id。
- [ ] 權限：`dangerous` 預設拒絕；每家公司各自 allowlist。
- [ ] 稽核 JSONL：`~/.local/state/mortal-mcp/audit/*.jsonl`；秘密欄位遮蔽。

## M2 背景工作

- [ ] `job_start / job_status / job_log_tail / job_cancel / job_list`；狀態存檔，重啟可查。
- [ ] 取消時先送 SIGTERM 給整個 process group，逾時再 SIGKILL（沿用 `server.py` 現有做法）。
- [ ] 進度：工具可輸出 `MORTAL_PROGRESS {json}` 行，status 取最後一筆。

## M3 精簡回傳

- [ ] 每個工具的 summary 規則：從輸出或 report.json 取計數與第一個錯誤；回傳上限（例 4 KB）。
- [ ] 完整日誌路徑一律回傳，不內嵌全文。

## M4 從 Fluke 工作抽出的新工具（2026-09-27～28 實際重複打過的 shell）

每個都先做成專案腳本（Fluke 專用放 Fluke repo `scripts/`，通用放 `~/tools/`），登記後再接 MCP。

- [ ] **worktree_activity**（通用，read_only）：列出 cwd 在指定工作樹內的 codex/claude/godot/gateway 程序、啟動時間、最近 N 分鐘被改的檔案。
  - 起因：Fluke session 只查了一個 Codex 程序就斷定「只有我在改」，其實另一個 Codex 在同工作樹跑了 35 小時。
  - 做法參考：`pgrep -f 'codex|claude'` → `readlink /proc/<pid>/cwd` 比對；`find -mmin -N` 排除 target/.git。
- [ ] **git_unpushed_audit**（通用，read_only）：本地未推 commit 數、與 develop 的 ahead/behind、未推 commit 內的大檔（>5MB）與媒體檔清單、working tree 大小分布。
  - 做法參考：`git branch -r --contains <sha>`、`git rev-list --count A..B`、`git diff-tree -r --name-only <sha>` 過濾副檔名。
- [ ] **service_log_summary**（通用，read_only）：指定 systemd user unit 與時間範圍，去掉 ANSI 色碼，把 WARN/ERROR 依訊息與 `error=` 原因分組計數，UUID/ID 正規化。
  - 做法參考：`journalctl --user -u <unit> --since ... | sed 's/\x1b\[[0-9;]*m//g' | grep -oE 'error=...' | sed 's/<uuid>//' | sort | uniq -c`。
- [ ] **fluke_bot_soak**（Fluke，mutation，job）：自建 postgres 容器（名稱與埠不與 25432/8080 衝突）＋隔離 Gateway（`FLUKE_PLAYTEST_NPCS=1`，DB 名必須是 `fluke_v1_ledger_test`）跑 N 秒；回傳每分鐘完成手數、各桌手數與最後一手時間、BOT 拒絕原因計數、逾時數、帳務 `ledger_table_hand_receipts` 筆數、買入筆數、借貸不平交易數；結束刪容器。
  - 可能與既有 `run_isolated_godot.py --scenario ten-tables` 重疊：先比對，能擴充就不另寫。
- [ ] **pre_push_summary**（Fluke，read_only，job）：跑 `scripts/check.sh` 的 fmt-check / gate / clippy / test / build，每關回通過與否、錯誤數、前 5 個位置。
- [ ] 替既有 `existing_shell_only` 的 Fluke 工具（ten-tables、create-table、riichi-*、admin-*）接 MCP adapter。

## M5 測試、遷移、上線

- [ ] 每工具成功例＋失敗例；陰性對照（故意壞參數、故意佔鎖）必須變紅。
- [ ] `doctor`：依賴版本、服務可達、config 可解析、允許根目錄存在。
- [ ] 9 個現有 MCP 功能遷移並對照舊輸出；systemd 切換新版，保留回退指令。
- [ ] 更新 README、SKILL（`skills/`、`.agents/skills/mortal-mcp/SKILL.md`）與 `~/tools/tools.json`。

## 未來（第一版完成後才啟動）：公開 MCP 庫

使用者構想（2026-09-28）：除了自有工具，其他人可上傳 MCP，由 mortal 檢查安全性、可靠性、效能並保存。

- 範圍規則（使用者 2026-09-28 定）：使用者發行的 MCP 所有人可用；個人上傳的 MCP 只供上傳者自己的帳號使用。
- 私人工具：跑自動檢查即可，不需人工審核；不得冒用官方工具名稱；其他帳號看不到也呼叫不到。
- 若在 mortal 伺服器上執行私人工具：每帳號獨立沙箱，隔離檔案／資料／金鑰，限制 CPU、記憶體與時間。若在上傳者本機執行：mortal 只負責檢查與保存。

- 前提：自動檢查只能降低風險，不能保證安全；不得宣稱「通過即安全」。
- 信任等級分開標示：自動檢查通過（掃描、成功／失敗例、效能上限）→ 沙箱實跑通過（限網路／檔案／時間，記錄實際存取）→ 人工審核通過。
- 官方工具（所有人可用）須人工審核通過才上架。
- 版本簽章且不可改寫；更新必須發新版；可一鍵下架並通知已安裝者。
- 沿用第一版的執行器、權限分級、稽核與資源鎖，不另做一套。
