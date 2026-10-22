---
name: ssd-scan
description: 唯讀盤點本機 SSD 空間、可清候選與增長，供 Aletheia 或維運查詢。
---

使用前查現有狀態。啟動：`systemctl --user start --no-block ssd-scan.service`。讀結果：`python3 ~/tools/ssd_scan.py report`；進度：`python3 ~/tools/ssd_scan.py status`。

MCP adapter: `ssd_scan_start`、`ssd_scan_report`；服務未載入新版本時使用上述既有 CLI。不得自行重啟共用 MCP。

不提供刪除功能。候選只代表白名單與當時程序檢查通過；實際清理仍需授權及執行前重查。未知、權限不足、超限不當成 0。模型、資料庫、執行環境、個人檔案與未使用資料卷不自動刪除。

掃描 CPU 30%、記憶體 384MiB、總工作 10 分鐘上限；可 `systemctl --user stop ssd-scan.service` 停止，不影響 Aletheia。沒有新增自動清理排程。
