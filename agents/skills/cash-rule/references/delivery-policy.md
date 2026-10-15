# 已驗成果立即交付（使用者 2026-10-05 定）

做好且通過必要驗證的交付單位，立即在既有授權內交付可用版本，不等整個目標結束；測試完成不是交付。

- 交付綁同一版本、驗證原件、可用入口；已授權部署要核實際讀回。沒授權就交可審閱版本並列「正式部署未授權」。無法交付列原因、失敗證據、下一步，不造可用入口。部分交付不把整體 step／task 標完成。
- Stop 入口 `finish_check.py` 呼叫 `delivery_check.py`：回答宣稱完成且驗證通過時，先保存 JSON 收據，回答獨立一行 `交付收據：<JSON路徑>`。收據：`schema_version:1`、`cwd`、`session_id`、`units[]`；每項 `id`、`version{path,sha256}`、`validation{path,sha256}`（含非空 `checks` 全 pass）、`delivery.status` 為 `available`／`deployed`（附 `entrypoint` 與同版本 `readback`）或 `unauthorized`／`paused`／`read_only`／`failed`（附 `reason`、`next_action`、`evidence{path,sha256}`）。
- 檢查只讀檔、比指紋，不執行命令；收據相符不證原件真實或服務可達。最多三次收工阻擋。
