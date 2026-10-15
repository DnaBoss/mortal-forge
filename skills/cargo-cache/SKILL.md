---
name: cargo-cache
description: Rust 多工作樹的編譯快取盤點、共用與安全清理；建立工作樹、編譯前或收工時使用。
---

# Rust 編譯快取

同一個 repo 不論幾個工作樹只有一份 `target/`，不同 repo 不混用（使用者 2026-10-03／04 定）。

- 工具：`python3 ~/work_space/private/mortal-mcp/tools/cargo_cache.py audit --repo <工作樹>` 盤點 owner、工作樹與使用中程序；`adopt --repo <工作樹> --keeper <工作樹/target>` 指定保留快取，預設只預覽，使用者授權刪除才加 `--apply`，授權收工清理再加 `--allow-session-cleanup`。
- 自動：`~/.local/bin/cargo` 包裝程式把 `CARGO_TARGET_DIR` 導到該 repo 唯一的 target，獨立位置拒絕（結束碼 2）；PreToolUse 攔獨立快取；Stop 有新獨立副本或壞連結不得收工；SessionEnd 寫盤點紀錄，啟用的 repo 才背景清理（120 秒、同鎖、無重試）。
- 只處理 Git 登記工作樹的 `target/`；查不到程序使用狀態就不刪；來源碼、模型、資料、使用中執行檔不刪；保留快取的工作樹要先搬快取、更新連結再移除。
- 證據：共用 Git 目錄的 `cargo-cache*.json`；最近盤點 `~/.local/state/cargo-cache/status.json`；`mortal_cargo_cache_status` 讀最近收工紀錄。設定寫入不等於目前 AI 已載入新 hook。
