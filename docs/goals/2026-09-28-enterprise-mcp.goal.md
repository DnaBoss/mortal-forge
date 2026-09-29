# GOAL：MORTAL MCP 企業級工具服務

> 建立：2026-09-28，由 Fluke 工作 session 交接。執行 session 在本 repo 施工；Fluke 遊戲仍是主線，這裡只做讓 AI 省 token、少打 shell 的共用工具。

## 為什麼做

- 使用者規則：每次工作都要先查 MORTAL，順便把重複的 shell 步驟做成工具，並回報 MORTAL 的不足。
- 2026-09-27～28 Fluke session 手動重複打了大量 shell：隔離伺服器實跑、日誌分類計數、Git 大檔清理、推版前檢查。每次都花 token 重新推導。

## 現況（2026-09-28 查證）

| 項目 | 事實 | 來源 |
| --- | --- | --- |
| 正在跑的服務 | Python `server.py`（144 行），systemd `mortal-mcp.service`，`MORTAL_FLUKE_ROOT` 寫死 Fluke「優化」工作樹 | `systemctl --user cat mortal-mcp.service` |
| MCP 功能 | 9 個，全部寫死在 `server.py` 的 `ROUTES` 與各函式 | `server.py:28` 起 |
| 工具清單 | `~/tools/tools.json` 25 個，只有 5 個有 MCP 入口，其餘 `existing_shell_only` | `mortal_catalog` 輸出 |
| Rust 版 | `src/` 336 行：health、companies、catalog、resources；不能執行工具 | `src/service.rs` |
| 已知錯誤 | `mortal_catalog` 有結果時仍附「Empty catalog」提示 | `server.py:82` |
| 上鎖 | 全機一把 `fluke-operations-<uid>.lock`，任何兩個變更操作都互斥 | `server.py` `execute()` |

## 完成條件（全部通過才 COMPLETE）

1. **通用執行器**：工具只在 config 登記一次（固定 argv 模板＋參數 schema＋工作目錄規則＋權限級別＋逾時）即可經 MCP 呼叫；不必改伺服器程式。拒絕 schema 外參數、拒絕把清單文字當 shell 執行。
2. **背景工作**：超過 30 秒的工具以 job 執行：`start → job_id`、`status`（階段、進度、已耗時）、`log_tail`（有上限）、`cancel`。伺服器重啟後可查到已結束 job 的結果。
3. **資源鎖**：依資源宣告鎖（例：`fluke-isolated-pg`、`fluke-preview-8080`），不同資源可並行，同資源互斥；拿不到鎖回明確錯誤，不排隊不重試。
4. **權限分級**：`read_only` / `mutation` / `dangerous`。`dangerous` 預設拒絕，需 config 明確允許；多公司各自獨立。
5. **呼叫稽核**：每次呼叫寫一筆 JSONL（時間、呼叫者標識、工具、參數摘要、結果、耗時、job_id），不記秘密與 PII。
6. **精簡回傳**：每個工具回結構化摘要（計數、第一個錯誤、證據路徑），完整日誌只存檔。回傳大小設上限。
7. **多 repo／工作樹**：工具可指定目標 repo 與工作樹，限定在 config 允許清單內；提供「此工作樹還有哪些 AI／程式在工作」查詢。
8. **測試**：每個工具至少一個成功例、一個失敗例（陰性對照會變紅）；`doctor` 檢查依賴、服務、config。
9. **遷移**：現有 9 個 Python MCP 功能移到新執行器後行為一致，再停用 legacy Python；systemd 改跑新版且可回退。

## 停止線

- 不做 UI、不做雲端部署、不做帳號系統；呼叫者標識用本機 client 名稱即可。
- 不為假想工具預做抽象；只接 TODO 列出的工具。
- 完成後不自動擴充，由使用者另行啟動。

## 相關

- 待辦：[TODO](../TODO.md)
- 目前狀態：[LOOP](../loops/2026-09-28-enterprise-mcp.loop.md)
- 既有計畫：[package-plan](../package-plan.md)
