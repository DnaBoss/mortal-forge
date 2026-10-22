# AI 工具總表

需要盤點工具、找 Skill／MCP 或追查版本異動時讀本頁。

```sh
ai-tool-index scan
ai-tool-index search codegraph
ai-tool-index search --kind mcp
ai-tool-index status
ai-tool-index history
```

資料統一放在 `~/.local/state/ai-tool-index/`：SQLite 保存最近 100 次掃描，snapshot.json 提供查詢。原始設定不搬動，掃描不執行設定中的命令，也不呼叫付費 API。

支援 Codex、Claude、Gemini、Cursor、Windsurf 的常見使用者 MCP 設定；Codex／Claude Plugin 快取與安裝登記；共用及各 AI 技能；tools.json；PATH 常見 AI 程式；本機 Ollama 模型。專案設定由 scan --project 明列，之後沿用；不代表已掃完所有專案或其他電腦。JSONC 設定目前不支援，讀取失敗會明列並保留舊資料。

用途可搜尋；版本查不到留空。安裝、啟用、快取、過期與未知分開記錄。啟用來自設定，不是目前對話載入證明。未蒐集執行紀錄，所以最後使用、成功率、次數、費用維持未知。不能靠這份索引補算先前 Jev 帳單。

Skill 以實際路徑與內容摘要去重；不同 Plugin 版本的同名 Skill 不合併。Plugin 登記、安裝紀錄與各版本快取是不同觀察，因此總筆數不是唯一產品數。讀取失敗或未掃描的範圍保留過期資料，不誤報刪除；成功掃描確認消失才記移除。

MCP 使用獨立的 Rust 標準輸入輸出程式，只讀同一份 snapshot.json。沒有新增常駐網路服務，不重啟原 MORTAL MCP。安裝後 Codex／Claude 新對話才能載入新 MCP；本次對話不自動獲得新工具。

安裝入口：`python3 scripts/install-ai-tool-index.py`。先建置 `cargo build --bin ai-tool-index-mcp`。安裝備份位於 `~/.local/state/ai-tool-index/install-backup/`。沒有定時掃描、遠端同步、自動更新或移除工具。

驗證：`python3 -m unittest discover -s tools -p test_ai_tool_index.py -v`、`cargo test`、`cargo clippy --all-targets -- -D warnings`、`npm test`，以及安裝後真實 MCP 查詢。測試資料不含真實金鑰。
