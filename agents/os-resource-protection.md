---
id: os-resource-protection
version: 1
updated: 2026-09-24
host: Essence
scope: CPU / host RAM / Ollama / user workloads / Docker
---

# OS 資源保護

## 目的與保證邊界

讓列管工作避開兩個實體核心，並在主機記憶體不足前停止模型。這是已部署的限制與救援機制；**8 GiB 是緊急觸發線，不是任何瞬間都不會越過的容量保證**。

CPU 拓樸為 16 實體核心、32 執行緒。核心 0 的執行緒是 0／16，核心 1 是 1／17。一般使用者工作、Ollama、Docker／containerd、目前的本機 gateway 與 machine.slice 只能使用 `2-15,18-31`。

- 使用者工作包括 Orca、編譯、瀏覽器、登入 shell，也包括 KDE 桌面程序；桌面仍可使用其餘 14 個核心。
- 系統服務與核心可使用保留核心。未列管的新 system service、管理者手動操作仍可能使用；不是 OS 獨占或即時排程保證。
- Docker 目前採 systemd scope；既有 17 個 scope 已套用，新 `docker-*.scope` 透過共用 drop-in 繼承。本會話未新開容器；另觀察到其他工作新建的 `80b20b02...` 容器也繼承相同範圍。
- 新增本機訓練／RAG system service 時，必須加入同樣 CPU 限制；不能只限制 Docker daemon 而漏掉容器。

## 記憶體行為

容量以 GiB 計：1 GiB = 1024 MiB。

| 情況 | 動作 |
| --- | --- |
| 可用 RAM 少於 16 GiB | `localai` 拒絕新請求；Ollama 啟動前也拒絕，且不進失敗重啟循環 |
| 可用 RAM 小於等於 12 GiB | 先留下持久封鎖紀錄，再要求停止整個 Ollama；進行中的回答會中斷 |
| 可用 RAM 小於等於 8 GiB、模型程序還在 | 對 Ollama 全工作組送一次強制終止；其他程序由既有 earlyoom 救援 |
| 壓力回復 | 不自動解除封鎖、不自動載回模型；人工確認原因並恢復 |

監測直接讀 `/proc/meminfo` 的 `MemAvailable`，每次檢查完成後約一秒再執行，timer 精度 100 ms。取樣、排程、停止及 GPU 回收都有延遲；另一程序仍可繼續分配記憶體。因此不能宣稱整機永遠保留 8 GiB。

Ollama 最長正常停止等候改為五秒，其後由 systemd 終止殘留程序。壓力封鎖檔由 root 管理，跨重開機保留；先記錄嘗試，再分別記錄指令接受／失敗和是否已觀察到程序停止。指令失敗不盲目重試，錯誤會留在日誌及狀態檔，須人工處理。

直接呼叫已啟動 Ollama API 的客戶端，仍可繞過 `localai` 的接單前檢查；但低水位監測會停止整個服務。接單前檢查不代表已預訂足夠 RAM，也不防止兩個呼叫同時通過。尚未建立所有請求共用的強制接單代理。

### 整機最後防線

沿用已安裝的 earlyoom 1.9.0：保留原有 RAM 20%／12% 門檻，交換空間條件改成 100%／100%，不必等交換空間不足才救援。取消整個程序群連帶終止與 RSS 排名，改用原生 OOM 分數，加權偏好模型程序、避開核心桌面程序；偏好不是絕對保證。必要時其他工作仍會被終止，未儲存內容可能遺失。

此版本 `-M` 先依 MemTotal 轉成百分比，實際比較又使用 MemAvailable + AnonPages，故沒有用它冒充固定 12／8 GiB 線。[官方 main.c](https://github.com/rfjakob/earlyoom/blob/v1.9.0/main.c)、[官方 meminfo.c](https://github.com/rfjakob/earlyoom/blob/v1.9.0/meminfo.c)。

保護程式與 earlyoom 放在獨立的 `os-protection.slice`，避開既有 `system.slice` 的 20 GiB 回收門檻；該舊門檻仍適用 Ollama 等其他系統服務。既有 Ollama CPU 端 12／16 GiB 上限與 GPU 載入餘裕保持，詳見[模型策略](local-model-management.md)。

## 狀態、停用與恢復

```sh
/usr/local/libexec/ollama-memory-gate status
systemctl status ollama-resource-guard.timer earlyoom.service
journalctl -u ollama-resource-guard.service -u earlyoom.service --since '1 hour ago'
```

因壓力封鎖後，先停掉不必要工作、查明原因。確認可用 RAM 至少 16 GiB、Ollama 程序已停止，再執行：

```sh
sudo /usr/local/libexec/ollama-memory-gate resume
sudo systemctl start ollama.service
```

`resume` 只解除封鎖，不自動啟動。停止監測可用 `sudo systemctl disable --now ollama-resource-guard.timer`，但不會解除既有封鎖，也不會停掉 earlyoom。

## 檔案地圖與還原

| 用途 | 路徑 |
| --- | --- |
| 可維護原始程式 | `/home/cash/tools/ollama_management/memory_gate.py` |
| root 管理的執行檔 | `/usr/local/libexec/ollama-memory-gate` |
| 模型呼叫端 | `/home/cash/.local/bin/localai` |
| CPU 設定 | `/etc/systemd/system/{user.slice,machine.slice,ollama.service,docker.service,containerd.service,agent-pool-gateway-local.service,docker-.scope}.d/60-os-cpu-reserve.conf` |
| 模型啟動／停止規則 | `/etc/systemd/system/ollama.service.d/70-memory-admission.conf` |
| 保護排程 | `/etc/systemd/system/ollama-resource-guard.{service,timer}` |
| 保護工作組 | `/etc/systemd/system/os-protection.slice` |
| earlyoom 規則 | `/etc/default/earlyoom`、`/etc/systemd/system/earlyoom.service.d/60-os-protection.conf` |
| 壓力封鎖 | `/var/lib/ollama-resource-guard/blocked.json` |
| 本次證據／備份 | `/home/cash/.local/state/ollama-management/20260924-153901-os-reserve/` |

還原前先確認沒有其他人修改同一檔案。停止並停用新增 timer，依 `installed-files.json` 逐一刪除本次新增檔案或從 `backup/` 回復舊檔，並回復備份的 `localai`。不得使用 `systemctl revert` 移除他人的設定。

本次也對 `cpu-apply.json` 的 22 個單元加上即時限制；還原時對仍存在的單元執行 `sudo systemctl set-property --runtime <unit> AllowedCPUs=`，再清理本次產生的 `/run/systemd/system.control/<unit>.d/50-AllowedCPUs.conf`。已保存的主單元原始 AllowedCPUs 為空，Docker 宣告的 CpusetCpus 亦為空；未保存每個舊 scope 的原始即時屬性，還原前須再比對容器部署設定。執行 daemon-reload，重啟 earlyoom；確認模型共用者已停工後再啟動 Ollama。既有其他資源上限不屬於本次還原範圍。

## 驗證與未驗證

- 已讀回 22 個現有單元的有效 CPU 範圍；新 docker 類型 scope 繼承相同範圍。
- 陰性對照：列管工作指定 CPU 0 失敗；一般 OS 測試服務指定 CPU 0 成功。
- 模擬低 RAM 僅覆蓋測試程序的 `/proc/meminfo`：真實 Ollama 被停止、啟動被 ExecCondition 拒絕、人工解除後正常啟動。當時未載入任何模型；沒有實際耗盡主機 RAM。
- 七項程式檢查通過，零略過：16 GiB 邊界兩例、壞讀值拒絕、停止與緊急動作各一次、停止逾時留下失敗狀態、localai 拒絕時不發 HTTP、Python 語法。
- 未驗證：實際 GPU 高壓回收速度、8 GiB 時強制終止活躍模型、整機耗盡壓測、重新開機、完整容器建立流程、長期桌面操作與 RAG。
- 這次變更直接套用本機運行環境；未修改遠端正式環境、未重啟 Orca 或現有容器。
