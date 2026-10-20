# ECC 專項接入

| 何時讀 | 入口 |
| --- | --- |
| Rust 審查、修復、測試設計 | [ecc-rust](../../skills/ecc-rust/SKILL.md) |
| PostgreSQL 查詢、索引、鎖、結構變更 | [ecc-database](../../skills/ecc-database/SKILL.md) |
| API 契約變更 | [ecc-api](../../skills/ecc-api/SKILL.md) |
| 校驗版本或更新來源 | 本文件及 [manifest](manifest.json) |

## 安裝範圍

官方來源 https://github.com/affaan-m/ECC 完整 checkout 保存於 manifest 的 source_root，固定提交 76aaa77df6adc5b889e689007bf99b9a4f74af34。原始授權保留於該目錄 LICENSE。沒有執行 ECC 安裝器、上游腳本、外掛或掛勾。宿主只發現本機三份技能，agents/skills、Codex 與 Claude 的技能連結共用同一份來源。

每輪 cash-workflow 只注入選用條件，專項原文透過 load.py 按需讀取。本機限制先輸出，原文後輸出；讀取前檢查版本、路徑範圍與雜湊，失敗不輸出原文。這保證引用完整性，不保證模型一定遵守；行為須由具體任務驗收。

## 維持現況

專案測試、變異門檻、編譯包裝、定期檢視、交付與授權仍是唯一依據；不匯入 ECC 共通規則、派工設定、背景學習或第二套進度。資料庫的 Supabase 假設、API 範例格式及 Rust 的全量命令不能直接覆蓋專案契約。[本機限制](local-policy.md) 統一列差異。

## 經驗篩選

既有 lessons_context.py 現在讀宿主 JSON 的 cwd。單條經驗可加一行明確範圍：

```text
- projects: ["/absolute/project/root", "/absolute/worktrees/root"]
```

路徑正規化後依目錄邊界匹配；同名開頭的另一專案不匹配。未知 cwd、無效標記不載入該條並顯示略過數；未標記者沿用原來規則。近 30 天與已有防護排除維持；相關專案優先分配既有容量，輸出仍按原順序。這是路徑範圍，不自動猜測遠端 repo 或跨機器身份。新工作樹若在範圍外須明確登記，不能宣稱自動辨識。

## 更新與復原

更新時另存完整新版本，檢查啟用群組及其引用的差異；重算 manifest、跑完整校驗與固定案例，再切換。不得就地拉新版本或只改雜湊掩蓋差異。未選中的腳本不會被執行；有新依賴需重新審查。

本次變更前原件在 ~/.local/state/ecc-integration/20261019/before。復原只移除本次新增的選用段落與技能連結；對已改動檔案比較備份後逐段還原，不能整檔覆蓋後續他人修改。來源可保留供查證，不必刪除。

## 驗證

執行 `python3 tools/ecc/load.py --verify`、`python3 -m unittest discover -s tools/ecc -p 'test_*.py'`；經驗篩選測試在 agents/guards/test_lessons_context.py。技能校驗與宿主輸出另存本機驗收紀錄。固定案例只測有限行為，不代表產品缺陷率或 token 成本已改善。
