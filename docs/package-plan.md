# MORTAL 工具套件計畫

2026-09-27；使用者授權規劃與實作。沿用 mortal-mcp repo，不另開相同產品。

目標：做成可安裝的標準 Skill／Plugin 套件。Skill 是工作流入口，會呼叫本 repo 提供的 Rust MCP 服務、CLI、固定 Shell adapter 或其他 MCP tool。服務需可支援一間或多間公司；每家公司工具由 config 登記，不在 Skill 內硬寫。

## 第一版

1. `skills/` 放標準可安裝 Skill；`.agents/skills/` 只保留 repo-local 相容入口。
2. `plugin.json` 與 `mcp.json` 描述可分發 plugin 與 MCP 連線。
3. Rust 服務提供 `/health` 與 Streamable HTTP `/mcp`；Python MCP 只作 legacy fallback。
4. 多公司支援由 `MORTAL_CONFIG` JSON 控制，工具 adapter 必須固定、可審查、可設 read-only。
5. npm pack 白名單打包，不含憑證、.venv、logs、測試資料。名稱暫用 mortal-dev-tools，private=true，不公開發布。

## 驗收

隔離 home 與測試 repo 驗 install→重複 install→update→doctor→uninstall；保留既有文字；使用者修改受管內容後拒絕覆寫；缺服務如實報錯；實際 npm pack 及本機 npm 安裝後由 bin 執行；Rust `/health` 與 MCP initialize 可回應。不得啟動 AI、遊戲、DB 或重啟使用者 Gateway/Godot。

## 狀態

2026-09-27：目標改為標準 Skill/Plugin + Rust MCP 服務。已新增 `skills/`、plugin/mcp manifest、Rust service skeleton 與多公司 config 範例。legacy Python adapter 暫留，後續逐項移植工具到 Rust。

第一次服務重載後 smoke 過早連線失敗；確認 systemd active 及後續真查詢成功後，再完整重驗通過。SKILL 驗證器原 venv 缺 YAML，改用已安裝 YAML 的系統 Python 後通過，未修改驗證器。證據 artifacts/npm-test.log、mcp-smoke.json、doctor.json、pack.json。
