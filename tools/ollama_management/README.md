# Ollama 狀態與有界驗證

共用策略：[本機模型管理](/home/cash/.agents/local-model-management.md)。

| 工具 | 適用時機 | 副作用 |
| --- | --- | --- |
| `status.py` | 查服務、記憶體、GPU 可見用量與已載入模型 | 一次唯讀 API；不載模型 |
| `probe.py` | 設定變更後確認指定模型能短答並記錄壓力 | 一次合成請求；會載模型並依服務預設保留 |

```sh
python3 /home/cash/tools/ollama_management/status.py
python3 /home/cash/tools/ollama_management/probe.py --model qwen3-coder:30b --output /tmp/ollama-probe-new.json
```

probe 每次只送一個請求，最多 16 個輸出文字單位、32768 對話暫存設定、120 秒 HTTP 上限；輸出檔必須不存在。取樣只讀本機檔案，不輪詢模型 API。

停止條件：主機可用 RAM 低於 20 GiB、主機記憶體全面阻塞 avg10 高於 10%，或總時間超過 125 秒，結束測試的 HTTP 程序。服務端是否已取消須另查，不能假設關閉連線就已卸載。

成功須 HTTP 成功、最後回覆 done=true 且回答非空；失敗退出非零，不重送。不存在模型可作負向對照，不會自動下載。

此工具不測模型回答品質、不驗最長提示、不測全服務爆量，也不是常駐防護程式。JSON 包含固定測試回答與資源樣本，不接收使用者私有文件。


## 常駐 OS 保護

[完整策略與恢復方式](/home/cash/.agents/os-resource-protection.md)。

`memory_gate.py` 是維護來源；運行版本由 root 安裝為 `/usr/local/libexec/ollama-memory-gate`。更新來源後須以 `sudo install -m 755` 同步，不直接讓 root 執行使用者可改寫的來源。

- `check`（預設）：可用 RAM 至少16 GiB且無封鎖才回0；錯誤／封鎖回1，不發模型請求。
- `status`：唯讀顯示RAM及封鎖原因。
- `tick`：限root，由systemd timer每次完成後一秒觸發；12 GiB停止Ollama、8 GiB仍有模型程序時強制終止。副作用會中斷生成。
- `resume`：限root，至少16 GiB且程序已停才解除封鎖，不自動啟動模型服務。

`localai`呼叫前及Ollama服務啟動前使用同一安裝入口；直接API仍可能繞過接單前檢查。沒有真正預約RAM，也不能保證瞬間不越過8 GiB。
