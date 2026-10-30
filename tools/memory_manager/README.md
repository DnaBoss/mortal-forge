# 持續管理記憶體

第一版每 30 秒主動把 cash 的程式群組中近期少用的記憶體換到 zram。zram 用 RAM 壓縮儲存資料，不寫 SSD。沒有記憶體壓力也會執行，不關閉程式、不刪檔、不清除全機檔案快取。

每個群組最多要求回收 128 MiB，每輪合計最多 256 MiB；實際回收量由核心決定，可能不足或超過要求量。至少觀察兩輪，保留 64 MiB 冷頁及 1 GiB 空閒交換區。兩輪皆列為冷頁只是候選判斷，不代表這些頁面一定不會再用；若已換出的頁面又被使用，下一輪暫停該組。等待記憶體或磁碟忙碌只作煞車，不是啟動條件。

範圍包含 user@1000.service 下面的 scope 與 service，父群組已涵蓋子群組就不重複處理。不包含系統服務、其他使用者及 GPU 記憶體。Ollama 只讀取目前模型與到期時間，沿用其自身卸載機制；不強制停止生成，也不承諾處理全部 43 GiB。若交換區有磁碟或 zram 啟用磁碟寫回，拒絕主動回收。

## 查看與停用

```sh
python3 ~/tools/memory_manager/manager.py --status
python3 ~/tools/memory_manager/manager.py --dry-run
systemctl --user status aletheia-cold-reclaim.service
systemctl --user stop aletheia-cold-reclaim.service
systemctl --user disable --now aletheia-cold-reclaim.service
```

狀態寫在 `/run/user/1000/memory-manager/status.json`，位於記憶體，不累積 SSD 日誌。`requested` 是要求量，`observed_anon_decrease` 是本輪前後觀察到的程式記憶體下降，其他程式同時運行，不能全當成回收器成果。每組列出回收前後用量、交換量、失敗與暫停原因。狀態超過 90 秒或本輪整體失敗時，`--status` 回傳非零。日誌每 10 分鐘一筆摘要，錯誤即時記錄。

沿用原本服務名稱，啟動鎖可防止重複執行。執行個體停止時，其回收子程序一起停止。已啟用使用者登入後啟動，也與 Aletheia 一起啟停；重開機實測須另驗，設定存在不代表驗過重開機。

## 驗證與恢復

```sh
uvx --offline ruff format --check ~/tools/memory_manager
uvx --offline ruff check ~/tools/memory_manager
python3 -m unittest discover -s ~/tools/memory_manager -v
```

舊腳本與服務備份保存在 `~/.local/state/memory-manager-v1/`。恢復時先停新服務，複製備份回原位置，執行 `systemctl --user daemon-reload` 後再啟動。不要同時開新舊兩套。

核心行為依據：[Linux memory.reclaim 官方說明](https://docs.kernel.org/admin-guide/cgroup-v2.html#memory)。使用 `swappiness=max` 只回收程式記憶體，不主動回收檔案頁。模型生命週期依據：[Ollama API](https://github.com/ollama/ollama/blob/main/docs/api.md)。

SSD 寫入原因追蹤、GPU 自動卸載、全機系統服務管理與產品介面不在第一版範圍；未做長時間效能與 SSD 寫入量驗收。
