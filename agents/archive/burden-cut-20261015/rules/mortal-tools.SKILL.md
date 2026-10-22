---
name: mortal-tools
description: 跨專案搜尋及復用既有 Shell、小程式與 MORTAL MCP；要重複檢查服務、執行固定驗收、建立工具或尋找已有自動化時使用。
---

先搜尋既有工具，勿因不同 repo 或 AI 重寫同一流程。

- 簡單 rg、讀檔、git diff 或單次編譯：直接 Shell。
- 重複多步操作：復用固定腳本；通用工具留工具 repo，專案腳本留原 repo。
- 啟停服務、隔離驗收及共用操作：優先已登記 MCP，保留鎖、逾時、證據與原授權。

MORTAL MCP：`http://127.0.0.1:18765/mcp`。先 `mortal_catalog` 搜用途，再依結果讀 `mortal_guide`；清單標示沒有 adapter 的工具使用既有 Shell 入口，不臆造 MCP 名稱。危險或會呼叫模型的工具不因登記便獲准執行。Godot 渲染中不可啟動本機推論。

未掛載 MCP 的 session：`node ~/.local/share/mortal-tools/package/bin/mortal-tools.mjs call mortal_catalog --arguments '{"query":"fluke"}'`。需要 Node 22、uv 及本機服務；缺依賴先回報，不重新造 client。`doctor` 檢查依賴與 MCP；`connect` 顯示各 AI 的註冊命令，新 session 是否載入須另外確認。

服務不可達時可讀 `~/tools/tools.json`（若存在）或套件內專案 SKILL 查固定腳本；不可啟動另一份相同服務來重試。新增共用工具需附用途、參數、讀寫影響、上限及測試，先登記後選擇是否包 MCP；不得把清單文字當成可執行 shell。
