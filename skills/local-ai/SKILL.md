---
name: local-ai
description: On host Essence, dispatch every piece of work (reading, drafting code, review, test analysis) to local Ollama models through localai / localai_dispatch, verify the answer, and record lessons. Use at the start of any task on this machine.
---

# 本機 AI 派工（主機 Essence 專用）

規則來源：`~/.agents/skills/cash-rule/references/model-dispatch.md` 第一節。別台電腦不適用。

## 流程

1. 開工先讀 `~/.agents/lessons.md`，避免重犯已記錄的錯。
2. 查資源：`python3 ~/tools/ollama_management/status.py`。可用記憶體不足或壓力升高時先等，不繞過 memory gate。
3. 派工（MCP 優先）：
   - `localai_dispatch(role="code", task=..., paths=[...])`：寫程式或修補。
   - `localai_dispatch(role="review", ...)`：審查。
   - `localai_dispatch(role="second", ...)`：第二意見。
   - Shell：`localai code --timeout 300 "<任務>" 檔案...`
4. 監督者驗證輸出：跑測試、陰性對照、讀差異。模型回答只是線索。
5. 犯錯就追加到 `~/.agents/lessons.md`：錯誤、原因、防止方式、日期。

## 注意

- 預設關閉隱藏推理，輸出上限 2048 個字詞。需要深推理才加 `--think`，並拉長逾時。
- 逾時先看 `journalctl -u ollama --since -10min` 的產生字數與載入狀態，不要直接重送。
- 任務只帶差異與必要檔案；不送憑證、`.env` 或個資。
- 服務上限：CPU 12 核、記憶體 12G 開始回收、16G 硬上限，最多同時載入 2 個模型。不要自行放寬到會讓整機滿載。
