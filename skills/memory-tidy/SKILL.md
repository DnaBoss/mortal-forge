---
name: memory-tidy
description: 本機記憶體被吃滿、已用超過 20G 時使用。一次檢查並釋放：閒置 claude／codex（先寫收尾記錄）、孤兒開發伺服器、/tmp 舊檔。
---

# 記憶體整理

## 什麼時候用

- 使用者說記憶體一直被吃、已用超過 20G。
- 想知道記憶體被誰用掉，或想關掉沒在用的 AI 終端機。

## 一次跑完

`python3 ~/tools/mem_tidy.py` 預覽；使用者同意後 `python3 ~/tools/mem_tidy.py --apply`。依序跑 idle_agents、orphan_servers、tmp_cleanup，前後各印一次「已用」。任一步失敗，整體結束碼為 1。

## 單獨使用閒置 claude／codex

1. 看記憶體拆解：`python3 ~/tools/idle_agents.py --report`
   「快取」不算佔用，系統需要時會自動讓出。只看「已用」。
   這台是 AMD Strix Halo，GPU 直接用系統記憶體，所以有「GPU 共用記憶體」一項，程序清單看不到它。
2. 預覽哪些閒置：`python3 ~/tools/idle_agents.py`
   預設門檻 4 小時，可用 `--min-idle-hours` 調整。這一步不會動任何程序。
3. 使用者同意後才關：`python3 ~/tools/idle_agents.py --apply`
   每個要關的程序先寫收尾記錄，寫成功才送 SIGTERM；寫失敗就保留。

## 它怎麼判斷閒置

- claude：`~/.claude/sessions/<pid>.json` 的狀態是 idle，且最後更新超過門檻。
- codex：程序開著的 rollout 對話檔，最後修改超過門檻。
- 不會關：自己的上層程序（正在跑這個工具的對話）、codex app-server。

## 收尾記錄

寫在 `~/.local/state/idle-agents/handoffs/`，內容有任務、最近的使用者指示、最後一則 AI 回覆、git 分支與未提交修改、還原指令。
記錄是從對話檔整理的，不呼叫模型。關閉不會刪檔，未提交修改仍在原目錄。

## 2026-11-04 盤點結論

除了上面三項，其餘佔用都是使用中的桌面程式（plasmashell、orca-ide、dolphin 等，各約 100–700MB）、Docker 服務和仍在用的 MCP 小程序（每個約 10MB），不建議自動關。要再省，只能關更多 claude／codex 或分頁。

## 限制

- 只看對話檔和程序狀態；有背景編譯或長時間指令在跑但畫面閒置的 claude，仍可能被判為閒置。關之前看預覽的 rss 與目錄。
- 實測過預覽與 `--apply`（2026-11-04，關閉 7 個）；沒有自動化測試。
