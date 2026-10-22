---
name: ecc-rust
description: Rust 程式審查、編譯錯誤修復或測試設計時，使用已固定版本的 ECC 專項指引，沿用專案品質門檻與共用編譯限制。
---

# Rust 專項能力

先讀目標專案規則，明確區分審查、已授權修復與測試設計。這是 cash-workflow 下的參考，不另開工作流程。

執行以下讀取器，將本機限制與校驗過的參考一起載入；只選當前需要的一組，不直接呼叫上游代理：

```sh
python3 /home/cash/work_space/private/mortal-mcp/tools/ecc/load.py rust-review
```

- `rust-review`：審查指定差異；含 rust-reviewer 與 rust-patterns。
- `rust-build`：已有編譯錯誤且任務授權修復；含 rust-build-resolver 與 rust-patterns。
- `rust-test`：需要設計測試案例；含 rust-testing。既有測試方法優先，不因範例新增套件。

上游的模型、工具、強制全部測試及比較分支只是其預設值。沿用目標專案命令、原有變異門檻與同版證據；遵守共用編譯目錄及資源限制。不要為了改錯誤訊息刪除測試、保留假未使用變數、升版或全面更新依賴。

交付問題位置、可重現情境、修復範圍及已跑／未跑驗證。風格建議與行為缺陷分開；校驗失敗回報原文，不自行更新來源。
