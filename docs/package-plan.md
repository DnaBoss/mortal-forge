# MORTAL 工具套件計畫

2026-09-27；使用者授權規劃與實作。沿用 mortal-mcp repo，不另開相同產品。

目標：一次安裝共用 SKILL、工具和 MCP 入口，各 repo 可發現及復用。npm 負責分發，SKILL 決定 Shell／腳本／MCP，服務仍限本機。第一版 Linux/macOS；Windows 服務管理未驗。

## 第一版

1. 零 npm 執行依賴 CLI，install/update/uninstall 管理全域 SKILL 與規則區塊；複製到穩定的使用者目錄，不依賴 npx 暫存。拒絕覆蓋非本套件內容，保留原文件及修改。
2. init/uninit 只管理指定 repo 的 AGENTS.md／CLAUDE.md 專屬區塊，不複製工具到各 repo。
3. doctor 檢查安裝完整性、工具依賴與服務 HTTP；call 沿用既有 MCP SDK 客戶端。connect 輸出官方 CLI 註冊命令，不猜改客戶端 config。serve 透過 uv 啟動固定 Python 服務；既有 systemd 服務原地保留。
4. 先包裝現有 Fluke 工具，另加跨專案工具目錄／SKILL 查詢；工具目錄不是任意 shell 執行白名單。~/tools 既有程式不整批搬移，依實際復用逐項收進 tools/ 或 adapter。
5. npm pack 白名單打包，不含憑證、.venv、logs、測試資料。名稱暫用 mortal-dev-tools，private=true，不公開發布。

## 驗收

隔離 home 與測試 repo 驗 install→重複 install→update→doctor→uninstall；保留既有文字；使用者修改受管內容後拒絕覆寫；缺服務如實報錯；實際 npm pack 及本機 npm 安裝後由 bin 執行；既有 MCP HTTP status 回歸。不得啟動 AI、遊戲、DB 或重啟使用者 Gateway/Godot。

## 狀態

第一版本機安裝包已完成驗證：Node 5/5（含真 npm pack/install/uninstall）、MCP 8項檢查、doctor 依賴／連線與 SKILL 格式檢查通過。全域 SKILL／規則已安裝；使用者後續注入的 AGENTS 指示已包含共用入口。未公開發布、不建立 cron。connect 只提供註冊命令，未自動改客戶端連線；未驗 Windows／其他主機或所有 AI 自動發現。非所有已登記工具均有 MCP adapter，查詢如實標示。用量無本步獨立來源，unavailable。

第一次服務重載後 smoke 過早連線失敗；確認 systemd active 及後續真查詢成功後，再完整重驗通過。SKILL 驗證器原 venv 缺 YAML，改用已安裝 YAML 的系統 Python 後通過，未修改驗證器。證據 artifacts/npm-test.log、mcp-smoke.json、doctor.json、pack.json。
