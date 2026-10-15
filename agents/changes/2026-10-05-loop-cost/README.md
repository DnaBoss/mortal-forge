# 2026-10-05：Aletheia 自動續跑失控檢討與限制改動

## 起因

使用者要求把兩站 CloudWatch 資料接入正式 Aletheia。代理人反覆補測試、文件與小修，已做真資料隔離實收，卻一直沒有交付正式接通。使用者多次反映 TOKEN 浪費，最後明確要求停止 LOOP。原任務已暫停，本次調查不恢復它。

問題不只是缺少 Prompt：代理人沒有及時收斂；沒有預算的持續任務又不斷收到自動續跑通知，放大了失誤。

## 查到的事實

1. 本對話的程序鏈是 Orca → Codex standalone → Codex app-server 0.160.0。程序實體位於 `~/.codex/packages/`。這證明誰在運行，不代表已讀到續跑實作原始碼。
2. `~/.codex/hooks.json` 確實登記 PreToolUse 檢查，包含 `~/.agents/guards/write_guard.py` 與共用編譯快取檢查。對話中曾收到真實拒絕訊息；不是虛構入口。
3. 唯讀查詢 `~/.codex/goals_1.sqlite`：本任務 status=paused，token_budget=NULL，tokens_used=2206451。這是程序記帳數字，不是已核實的帳單或費用。
4. 從正在使用的 Codex 執行檔匯出正式介面格式，確認有 `thread/goal/set`、`tokenBudget`、`budgetLimited`。格式檔只能證明介面存在，尚不能證明超額時停在何種邊界、是否可能超額一輪。
5. 因此先前「改設定檔即可控制排程器」的說法過度簡化。並未找到可直接修改的續跑程式碼，也未建立另一套排程器。

## 本次實際修改

- 新增 `~/.agents/guards/goal_budget_guard.py`：直接 create_goal 請求必須提供正整數 token_budget。缺值、零、負數、布林值、字串均拒絕；讀取與暫停放行。
- 在 `~/.codex/hooks.json` 的 PreToolUse 清單追加上述檢查，原項目保留。
- 修改前完整設定保存為本目錄 `hooks.before.json`。
- 新增本目錄 `test_goal_budget_guard.py`，四項離線測試通過。
- 登記 `~/tools/tools.json`，名稱 codex-goal-budget-guard。
- 沒有修改 GOAL 資料庫、原任務預算或暫停狀態；沒有重啟服務、建立付費試跑或修改 Aletheia。

## 效力邊界，不能省略

這是已安裝的檢查設定，不是已證明全面生效的成本防線。目前未證明 Codex 將內建 create_goal 派送給 PreToolUse；內嵌 functions.exec 的 JavaScript 與其他客戶端不在此檢查範圍。不能因此聲稱無上限 GOAL 已完全被擋。

原生 tokenBudget 是真正應採用的成本限制。需要由使用者指定數字，再透過原生介面設定，不能由代理人猜預算。尚未修改所有新任務的預設策略，也沒有假設此 hook 能停止模型產生回覆。

進度是否有效、重複測試是否合理，尚未加機械限制；不能以 AI 自填「有進展」當硬證據。限制程式與設定目前同屬使用者帳號，亦非能抵抗任意改寫的安全隔離。

## 驗證與退回

離線指令：`python3 ~/.agents/changes/2026-10-05-loop-cost/test_goal_budget_guard.py`。

如需退回，只從 hooks.json 移除 command 為 `/usr/bin/python3 /home/cash/.agents/guards/goal_budget_guard.py` 的新項目；不要整份覆蓋備份，以免抹掉後續其他人的修改。保留此紀錄及測試。

原生格式證據在 `~/.agents/evidence/loop-cost-20261005/schema/`；本次唯讀結果在 `facts.json`。未進行新的 GOAL 實際建立測試，以免啟動另一個消耗任務。
