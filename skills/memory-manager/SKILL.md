---
name: memory-manager
description: 查看 Essence 常駐記憶體管理的狀態、驗證與恢復方式。
---

先讀 `/home/cash/tools/memory_manager/README.md`。狀態用 `python3 /home/cash/tools/memory_manager/manager.py --status`，唯讀盤點用 `--dry-run`；沿用 `aletheia-cold-reclaim.service`，不可另開回收程序。

目標是持續降低不必要占用，不以有無壓力判定需不需要管理。群組壓力只作回收煞車。不得把服務存活或要求回收量當成實際效果；要查回收前後用量與錯誤。

不關程式、不清檔、不卸載使用中的模型、不啟用磁碟交換。GPU 與系統服務不在本版主動管理範圍。修改或啟停需沿用當前任務授權。工具已登記 `~/tools/tools.json`，目前無 MCP 寫入 adapter，使用固定 Shell 入口。
