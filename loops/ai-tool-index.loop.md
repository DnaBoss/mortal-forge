# AI 工具統一索引 LOOP

## 目標
統一查詢本機 AI 工具、Skill、MCP、Plugin、模型；保留掃描差異，不搬動原設定、不保存 MCP 秘密設定。

## 整體驗收
- [x] CLI 搜尋、狀態與歷史可用；真實 MCP 查詢成功。
- [x] 來源、版本及未知狀態分開；相同掃描 0 異動。
- [x] 新增、修改、移除與失敗保留舊資料通過；非法查詢及缺索引拒絕。
- [x] 本機安裝與檔案雜湊讀回通過；原有 AI 設定值完整保留。

## 計畫
| step | 成果 | 狀態 |
|---|---|---|
| inventory | 掃描、索引、差異、CLI、Skill、MCP、本機安裝 | DONE |

## 交付點
ai-tool-index.delivery.json 固定來源、安裝與讀回；本機交付已通過。

## 目前狀態
COMPLETE；獨立工作樹 feature/ai-tool-index。沒有掃描排程，未改正式環境或重啟原 MORTAL MCP。
493 筆觀察紀錄，含 332 Skill、21 MCP、58 Plugin 登記／版本紀錄、71 共用工具、7 應用、4 模型。不是唯一產品數。
9 項 Python、2 項 Rust、5 項 Node 測試及 Ruff／Clippy 通過。真實 MCP 正反例、設定保留與安裝衝突拒絕通過。
目前 AI 對話尚未載入新 MCP；新對話可用。其他未指定專案、其他機器、費用與最後使用紀錄尚未涵蓋。
交付收據：/home/cash/.local/state/ai-tool-index/delivery.json
checkpoint：ai-tool-index.checkpoints.jsonl
