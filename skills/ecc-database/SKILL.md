---
name: ecc-database
description: PostgreSQL 查詢、索引、鎖或資料結構變更需要設計或審查時，使用固定版本 ECC 指引；沿用專案資料模型、授權與驗收。
---

# 資料庫專項能力

先讀專案規則與資料模型，確認任務是設計、審查還是已授權修復；審查不自動連線或執行結構變更。

```sh
python3 /home/cash/work_space/private/mortal-mcp/tools/ecc/load.py database-review
```

- `database-review`：查詢、索引、鎖與安全審查；載入 database-reviewer、postgres-patterns、database-migrations。
- `database-migration`：設計結構變更及新舊版本相容；載入 database-migrations、postgres-patterns。

讀取器會先輸出本機限制再輸出校驗原文。上游 Supabase、auth.uid、RLS、索引、主鍵與資料型別建議須依現況判斷，不機械套用。EXPLAIN ANALYZE 會執行語句；先確認隔離環境與授權，不自行取用 DATABASE_URL。

保留交易、批次上限、冪等、原資料與現有驗收；不自動 migration、回滾或加索引。交付具體查詢／檔案、失敗情境、相容性、量測證據或未量測限制。校驗失敗不使用該份上游指引。
