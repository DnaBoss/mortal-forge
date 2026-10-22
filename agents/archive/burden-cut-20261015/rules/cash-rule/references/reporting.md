# 檢查點、通知與用量

唯一檢查點格式為 [`schemas/checkpoint.schema.json`](../schemas/checkpoint.schema.json)，版本跟隨 SKILL.md 的 `protocol_version`。Schema 驗單筆欄位與轉換；[驗證器](../scripts/validate_checkpoints.py) 依 `task_id` 核對任務狀態與連續序號，依 `task_id + step_id` 核對 `previous_step_state`，並拒絕終止任務後續寫入。checkpoint 時點唯一依 SKILL.md；多輪或持續任務將 JSON 追加到與主 LOOP 同目錄的 `<slug>.checkpoints.jsonl`；檔案路徑記在主 LOOP。短任務不建檔。JSONL 是歷史紀錄，追加後不改寫；錯誤不可用假接續掩蓋，需保留原檔，另開明確連結原紀錄的修正任務。1.1.0 歷史保持原樣；1.2.0 使用新串流，不混版、不自動猜補舊資料。

LOOP 只保留目前狀態的可讀投影：現在在哪、已證明、未證明、下一步、阻塞，以及 checkpoint 檔案位置。不得再複製每輪完整歷史或協定規則。

通知只在重大成果、需要決策的阻塞、重排、step 完成、風險／授權邊界改變或使用者要求時發送。一般每輪只更新 checkpoint，不必另發訊息。

## 用量模式

- `minimal`：一般工作預設。只記可取得的總耗時、實際派工／工具呼叫摘要，以及用量狀態與來源；用量拿不到就記原因，不為補數字讀取其他會話內容。
- `benchmark`：使用者要求比較成本、模型或流程時才開。必填 `benchmark.baseline_id` 與非空 `executors`；每位執行者必填 executor、model、calls、input_tokens、output_tokens、wait_seconds、execution_seconds、rework_seconds、outcome（used／edited／rejected）。所有數值採下述 measurement 格式；拿不到仍填 unavailable。minimal 禁止 benchmark。

執行中的每筆 checkpoint 必填 `acceptance`（對應的整體驗收編號）；決定為 `block`／`fail` 時必填 `stop_proof`，內容依 [停止舉證](stop-policy.md)。兩項由寫入工具對新紀錄把關，舊紀錄不補。

涉及外部研究時才填 `search_conclusion`：`found` 或 `not_found_within_scope`，並附搜尋紀錄；一般工程 checkpoint 省略這兩欄。

本機輸入字元記為 `local_only_input_chars`，描述資料量，不等於省下的雲端 token。只有指定了雲端基準模型、相同輸入與計算方法時，才能填 `avoided_cloud_tokens`，並在該 measurement 內記 `baseline_id`、`calculation_method`；它是反事實估算，只允許 estimated／unavailable，不允許 exact。否則省略或記 unavailable。

每個量測各自用 `{ "value": 8000, "status": "exact", "source": "provider response" }`，不再用整體 usage.status。狀態為 exact／estimated／unavailable；unavailable 的 value 必須 null 並用 source 說明缺口，其餘必須非負有限數。estimated 要附 method（avoided_cloud_tokens 改用 calculation_method）。token、字元與 calls 為整數。exact 需有供應商／執行器計數或時鐘等直接量測；來源文字本身不證明其真實性。usage 至少一個量測，無 token 來源時可記 input_tokens unavailable，不為補數字讀其他會話。數值為本 checkpoint 增量，不把累計快照相加；總時間另依任務起訖計算。

總經過時間以任務起訖計算；等待或中斷分開記，資料缺漏明列。記錄不應延誤主要成果，也不得包含秘密或其他工作階段內容。

## 機械驗證與安全記錄

- decision 是下一步行為：continue 只用於 DISCOVERING／PLANNED／RUNNING／VALIDATING／REVIEWING；replan→PLANNED、wait→WAITING、block→BLOCKED、monitor→MONITORING，其餘與對應終止狀態一致。
- actions 只用 `command_summary` 保存已遮蔽秘密、可重現意圖的表示，例如 `curl -H "Authorization: Bearer <REDACTED>" <URL>`。result 只寫摘要；完整 stdout/stderr 應先檢查並遮蔽秘密後另存 evidence artifact，以 locator 引用。改欄位名不是自動秘密掃描，其他字串也禁止秘密。
- 追加 checkpoint 一律用 `~/tools/cash-rule-checkpoint FILE --task T --step S --task-state ... --step-state ... --target "..."`：它讀上一筆自動接續狀態與序號、用時鐘蓋 `recorded_at`、寫入後整檔驗證，不合格就還原。不得手寫 JSON，不得用 echo／cat／tee／python 直接追加或改寫 `*.checkpoints.jsonl`；PreToolUse guard（`~/.agents/guards/write_guard.py`）會擋下。
- 驗證器只證明格式與已記錄狀態一致，不證明來源真實、未記錄的 step 不存在或工程成果完成。COMPLETE 仍須整體驗收；pass 不可搭配失敗／未跑 checks，需至少一個 check，必要的負向對照必須通過。
- 依賴安裝到隔離環境：`uv venv ~/.cache/cash-rule-validator`，再 `uv pip install --python ~/.cache/cash-rule-validator/bin/python -r scripts/requirements.txt`（在技能目錄執行）。
- 執行：`~/.cache/cash-rule-validator/bin/python scripts/validate_checkpoints.py <完整歷史.jsonl>`；成功 0、格式／接續錯誤 1。不寫回 JSONL，錯誤不回顯內容。測試：`~/.cache/cash-rule-validator/bin/python -m unittest discover -s tests -v`。
