---
name: orca-claude-env
description: ORCA 裡的 Claude Code 每則訊息都回「There's an issue with the selected model ... may not exist」，但同一台機器別的終端機正常時使用。查出 ORCA 背景程式帶著過期的 ANTHROPIC_BASE_URL，並安全修復。
---

# ORCA 裡 Claude Code 報「模型不存在」

## 症狀

- 在 ORCA 開的 Claude Code，連 `Reply exactly: OK` 都失敗，畫面顯示：
  `There's an issue with the selected model (claude-opus-5-5[1m]). It may not exist or you may not have access to it.`
- 同一台機器，在一般終端機（例如 konsole）開的 Claude Code，用同一個模型名稱卻正常。
- 換模型沒用。這個錯誤訊息會誤導人去查模型權限。

## 原因（2026-09-28 實際查證）

- ORCA 有一個背景程式，負責開 ORCA 裡的終端機。它的指令列含 `daemon-entry.js`。
- 當時那個背景程式是從舊版 `/opt/Orca` 啟動的，身上帶著 `ANTHROPIC_BASE_URL=http://127.0.0.1:18080`。
  這個設定叫 Claude Code 把請求送到本機的轉送服務（fluke-gateway），而不是 Anthropic。
- 那個轉送服務對 `POST /v1/messages` 回 `404`。Claude Code 收到失敗，就顯示「模型可能不存在」。
- ORCA 畫面本身（新版 AppImage）沒有帶這個設定。只有舊背景程式帶著，所以關掉 ORCA 視窗重開也沒用。
- 舊背景程式最早從哪裡拿到這個設定：查不到。`~/.zshrc` 裡這一行當時已經被註解掉。

## 處理步驟

1. **先查，不動手**：呼叫 MCP `orca_claude_env_check`。
   沒掛 MCP 時執行 `python3 ~/tools/orca_claude_env/orca_claude_env.py check`。
2. 看回傳的 `verdict.code`：
   - `stale_base_url`：就是這個問題。`stale_daemon_pids` 是要關的背景程式。
   - `base_url_set_gateway_answers`：有設定，但轉送服務有回應。這個工具解釋不了錯誤，要改查轉送服務本身。
   - `clean` 或 `no_daemon`：不是這個問題。改查帳號登入（`/status`）。
3. **警告**：關掉背景程式會關閉 ORCA 裡所有的 Claude Code。先跟使用者確認，並告訴他哪些對話會被關。
4. 使用者同意後，呼叫 MCP `orca_stop_stale_daemon(pid=...)`。
   工具只接受 check 回報為「過期」的 pid，其他 pid 一律拒絕。
   關之前，工具會把每個對話的資料夾和 `--resume` 編號存成 JSON，路徑在回傳的 `resume_list`。
5. ORCA 畫面會自動開一個新的背景程式。再呼叫一次 check，確認 `verdict.code` 變成 `clean`。

## 怎麼確認修好

- 在 ORCA 開新分頁，啟動 Claude Code，打 `Reply exactly: OK`。畫面只回「OK」就算修好。
- 陰性對照（證明原因找對了）：在一般終端機執行下面這行，必須重現同一個錯誤。
  ```
  ANTHROPIC_BASE_URL=http://127.0.0.1:18080 claude -p "Reply exactly: OK"
  ```
  注意：這行和上面的測試各會送一次很小的模型請求。
- 接回舊對話：到 `resume_list` 記的資料夾，執行 `claude --resume <編號>`。沒有編號的對話（例如團隊模式）要重開。

## 邊界

- check 只讀 `/proc` 和送一次不帶金鑰的空請求到轉送服務，不呼叫模型，不印出金鑰內容。
- check 通過只證明「背景程式沒帶錯的設定」。它證明不了帳號權限、網路或轉送服務本身正常。
- stop 只送 SIGTERM（請程式自己結束）。10 秒內沒結束就回報失敗，不會強制殺掉，也不會自動重試。
- 不要為了修這個去改 `~/.zshrc` 或 ORCA 設定檔。那是使用者的設定，只給建議。
