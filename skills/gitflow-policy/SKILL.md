---
name: gitflow-policy
description: Inspect and install recoverable Gitflow hooks for confirmed personal repositories; preserve existing gates and worktrees.
---

# Gitflow policy

使用者要求私人 repo 分支／commit／hooks 整理時使用。

1. 先確認 remote owner 與專案性質。排除 newretail、BK、account_linker；未確認歸屬不修改。
2. 讀 repo 的 AGENTS.md、DEVELOPMENT.md、現有技術規範與 `.repo-policy/config.json`。
3. 先記錄 HEAD、status、全部 worktree 與舊 hooks 設定，保留可靠備份。
4. 檢查 `python3 .repo-policy/test_policy.py`；從已審查的來源安裝 `python3 .repo-policy/install.py`。多 worktree 先逐一核對，才用 `--include-worktrees`。安裝會改共用 Git config，保留舊 hooks 並輸出復原紀錄。
5. 用 `mortal_repo_policy_status(repository="Fluke")` 做唯讀核對；若目前 service 尚未載入新版 tool，執行 `python3 ~/tools/gitflow-policy/policy.py audit ~/work_space/private/Fluke`。不要為了核對重啟共用服務。
6. 新工作從 develop 開 feature/ 或 bug/；release/、hotfix/ 使用完整版本。Conventional Commits、格式、lint、測試和既有較嚴 gate 不得繞過。

MCP 只接受固定私人 repo 名稱，沒有任意 shell、路徑、遠端或寫入參數。CLI audit 只有本地唯讀操作。安裝不啟動部署、不改 staging、不格式化檔案；不要把安裝、測試、CI、部署與驗收混稱完成。

有既有 baseline 失敗、合併衝突或會部署的 push，回報具體 action／target／原因，繼續其他獨立 repo。

復原使用 installer 的 `--restore <installation.json>`；需匹配原 checkout 及目前設定，否則拒絕覆寫。不要不可恢復刪除 hook 快照。
