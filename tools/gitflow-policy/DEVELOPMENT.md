# 開發規範

本文件定義所有私人 repo 的共通底線。既有架構、安全、資料授權、測試與覆蓋率要求繼續有效；有較嚴格的要求時遵守較嚴格者。專案差異與實際檢查命令記在 `.repo-policy/config.json`。

## Gitflow

| 分支 | 起點 | 用途與完成後流向 |
| --- | --- | --- |
| `develop` | 已確認的整合主線 | 整合通過檢查的工作；禁止直接一般 commit |
| `main`／`master` | 保留既有穩定分支 | 收已驗證的 release／hotfix 合併，不隨意改名 |
| `feature/<slug>` | 最新 `develop` | 新功能；完成後合回 `develop` |
| `bug/<slug>` | 最新 `develop` | 一般缺陷修復；完成後合回 `develop` |
| `release/<major.minor.patch>` | `develop` | 凍結版本，只做版本、文件與 release 修復；完成後合入穩定分支、打 `v<major.minor.patch>` tag，再同步回 `develop` |
| `hotfix/<major.minor.patch>` | 穩定分支 | 已發布版本的緊急修復；完成後合入穩定分支、打 tag，並同步回 `develop`／進行中的 release |
| `docs/<slug>`、`chore/<slug>`、`refactor/<slug>`、`test/<slug>`、`ci/<slug>` | 最新 `develop` | 單一目的維護；完成後合回 `develop` |

slug 用小寫英文、數字與 `-`，例如 `feature/search-filter`、`bug/expired-token`。release／hotfix 必須用完整語意版本；可附 `-rc.1` 等預發布版本。

開新工作先 `git fetch origin`，確認遠端 `develop`，再從 `origin/develop` 建立新分支。若工作樹不乾淨，保留內容並使用獨立 worktree，不 reset、clean 或 stash 別人的工作。

已有 `dev`、`feat/*`、`fix/*` 或歷史命名的工作，保留明確登記的相容清單；它們不代表新工作的命名範例。`dev` 與 `main` 已分歧的 repo，不能只因名稱相似就合併；先審查兩條主線的差異。

開始工作時，確認分支來源與工作用途。hooks 能檢查分支名、保護主分支與 push 的實際 commit，不能從分支名推斷完整業務意圖；合併前仍須 review 與驗收。先比較雙邊變更，有衝突或不同業務意圖時停止合併，記錄具體阻擋。

## Commit 與整合

使用 Conventional Commits：`type(scope): 說明`，scope 可省略，破壞相容性加 `!`。type 限 `feat`、`fix`、`docs`、`style`、`refactor`、`perf`、`test`、`build`、`ci`、`chore`、`revert`。

例：`feat(search): add saved filters`、`fix(auth): reject expired token`、`chore(repo): enforce Gitflow hooks`。

- 標題最多 100 字元，一個 commit 只做一個可說明的目的。
- 內文說明原因、影響、驗證與相容性；不要把 secret、憑證、資料列放進訊息。
- 不提交無意義的 `update`、`wip`、`fixup!` 或 `squash!`；整合前整理暫存 commits。
- hooks 接受真實 merge 的 Git 產生訊息；直接主分支 commit 不接受。
- 審查 diff、跑適用 gate 後整合。保留既有 fast-forward／PR 要求；release 需保留可辨識的版本歷史。
- 禁止 force push、改寫發布 tag。刪分支前核對遠端 tip 已包含在 `develop`，保留預設、主要、受保護與活躍 worktree 分支；squash 未有祖先證據時另外審查，不自動刪。

## 程式品質

沿用既有 formatter、lint、型別與測試工具。新增功能或修復需有能抓到錯誤的驗證，保留既有 gate、覆蓋率、架構與安全約束；不能降低門檻、吞錯或繞過 hooks 取得綠燈。

Rust 使用 rustfmt、clippy 與適用測試；Node／TypeScript 使用 package scripts；Python 先檢查語法，再跑專案既有測試。沒有程式的規劃 repo 不虛構 build/test；日後新增語言時同時更新 policy checks。既有工具鏈鎖定繼續有效，不因本機較新就更改。

只修改授權的範圍；不用規範整理順便改架構或產品功能。文件裡的命令、路徑與描述要符合實況。不得提交 `.env`、本機 DB profiles、憑證與 runtime 狀態；範例需使用 `.env.example` 等明確名稱。

## Hooks

需要 Python 3.10+、Git、bash，以及專案原本使用的工具。取得本分支後執行：

```sh
python3 .repo-policy/install.py
python3 .repo-policy/policy.py audit .
python3 .repo-policy/test_policy.py
```

有多個 worktree 時先逐一核對狀態與現有 hooks，再用 `python3 .repo-policy/install.py --include-worktrees`。`core.hooksPath` 是共用 Git config；這個選項會把保護套用到同 repo 的所有 worktree，不修改它們的檔案。不要重複安裝；升級先用復原紀錄還原，核對新版再裝。

- `pre-commit`：檢查分支、staged whitespace、敏感檔名與明顯私鑰、Python／JSON／shell 語法，再執行符合變更語言的快速 gate。涉及專案 gate 的部分暫存內容需先完成 staging；不自動格式化、不修改 index。
- `commit-msg`：強制檢查 commit 標題格式。
- `pre-push`：從 Git 傳入的真實 ref／SHA 檢查非 fast-forward、命名、發布 tag、主要分支刪除與新 commit 訊息；適用語言的完整 gate 必須成功。每次推送只接受目前 checkout 的 commit；tracked 工作樹要乾淨，才能保證檢查的是 outgoing tree。
- 安裝使用 Git metadata 內的獨立版本快照；原 hooks 不覆寫，仍串接執行。其他既有 hook 也保留。切換至尚未含 policy 檔案的歷史分支仍有保護。

安裝輸出含 `installation.json` 路徑。復原使用：

```sh
python3 .repo-policy/install.py --restore /實際/Git/metadata/repo-policy/版本/installation.json
```

原 config 與 hooks 都有紀錄，快照留作復原證據。請勿使用 `--no-verify` 或清空 `core.hooksPath` 繞過失敗。hook 失敗需修正原因，或明確回報既有 baseline／環境阻擋。

hooks 是本機檢查，可由具有 repo 寫入權限的人修改；它們不取代 GitHub branch protection、CI 或 code review，也不宣稱已替伺服器設定保護規則。

## 部署邊界

push 會自動部署／發布的分支記在 `deployment_branches`；本套 hooks 拒絕這些 push。release 執行者沿用使用者的持續部署授權，完成必要測試後走既有發布流程，不必再次詢問；不在一般開發過程解除分支保護。文件或 tests 通過不代表已部署、部署健康或使用者驗收完成。

本次規範整理不啟動部署、不送單、不連正式 DB，不修改 GitHub Actions 的部署觸發條件。
