# 跨 AI 共用工具

位置：`~/tools/`（本機實際路徑 `/home/cash/tools/`）。其他主機需各自同步，不能假設已安裝。

## 查清單

本機模型的共用、記憶體與未來 RAG 管理規則：[本機模型管理策略](/home/cash/.agents/local-model-management.md)。設定變更前先讀；實際狀態與驗證工具見 [ollama_management/README.md](ollama_management/README.md)。

唯一程式清單：[tools.json](tools.json)，包含用途、位置、用法、輸入輸出、依賴、風險與驗證紀錄。

```sh
python3 ~/tools/list_tools.py
python3 ~/tools/list_tools.py 搜尋
python3 ~/tools/list_tools.py --check
```

`--check` 只查登記位置是否存在、PATH 指令能否找到，不執行工具，也不表示功能驗證通過。
搜尋沒結果回傳狀態碼 1，清單損壞或工具缺失回傳 2。

## 維護

先查清單再建工具。可跨專案重用的通用程式放本目錄，專案腳本留原 repo 並登記絕對位置。
已有 rg/codegraph/localai 只登記，不搬動、不複製或重裝。
新增可重用程式須更新 tools.json，各欄位不可省略；不可存金鑰、帳密或敏感輸出。
小樣本與失敗案例通過才擴大使用；新增清單不代表該工具已通過實際功能測試。
批次仍遵守原授權、DB／遠端一次批次規則；刪除仍須明確授權；部署已有持續授權，完成必要測試後直接進行，不必再次詢問。

驗證清單程式：`python3 ~/tools/test_list_tools.py`。
