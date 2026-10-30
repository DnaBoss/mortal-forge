# 紀錄與通知（2026-10-15 精簡）

- checkpoint 格式唯一是 [`schemas/checkpoint.schema.json`](../schemas/checkpoint.schema.json)；只准用 `~/tools/cash-rule-checkpoint` 追加，它接續狀態與序號、寫入後整檔驗證、不合格就還原。手寫或 shell 追加由 `write_guard.py` 擋。JSONL 只追加不改寫。
- 只在狀態變化或有新證據時寫；重複筆被工具拒收。執行中必填 `acceptance`；`block`／`fail` 必填 `stop_proof`；`wait` 必填 `wait_on` 與 `wait_tried`。
- 不記每輪用量；token 事後用 `~/tools/cash_rule_burden.py` 從對話紀錄算。
- LOOP 只保留目前狀態投影（整檔不超過 3,000 字元），不複製歷史與規則，不開 step LOOP；跨喚醒續行記 owner lease（見 [執行](runtime.md)）；LOOP 記 checkpoint 檔路徑。
- 通知只在重大成果、需決策的阻塞、重排、step 完成、授權邊界改變時發；一般每輪只更新 checkpoint。
- 紀錄不含秘密與其他工作階段內容。驗證器：`~/.cache/cash-rule-validator/bin/python scripts/validate_checkpoints.py <jsonl>`；它只證格式與狀態接續，不證成果完成。
