---
name: cargo-cache
description: Rust 多工作樹的編譯快取盤點、共用與安全清理；建立工作樹、編譯前或收工時使用。
---

# Rust 編譯快取

同一 Git repository 的工作樹共用一份 `target/`，不同 repository 不混用。
使用 `mortal_cargo_cache_status` 讀最近收工紀錄；時間戳代表上次盤點，不代表即時狀態。

## 盤點與採用

工具位置：`~/work_space/private/mortal-mcp/tools/cargo_cache.py`。

1. 執行 `python3 <工具位置> audit --repo <工作樹>`，確認 owner、所有工作樹與使用中的程序。
2. 指定要保留的實體快取：`python3 <工具位置> adopt --repo <工作樹> --keeper <工作樹/target>`。預設只預覽。
3. 使用者已授權刪除重複編譯產物時，加 `--apply`；同時授權收工清理時加 `--allow-session-cleanup`。
4. 核對刪除前後實體份數、占用容量、刪除／略過紀錄，以及各工作樹的共用連結。

只處理 Git 登記工作樹的 `target/`，須有 Cargo 標記、沒有受 Git 追蹤的檔案、內容符合編譯快取。
拒絕外部保留路徑、不明內容與不明連結。查不到程序使用狀態就不刪；必要的 sudo 僅用於只讀程序檢查。
來源碼、模型、訓練資料與正在使用的執行檔不得刪除。不可移除保留快取的工作樹，除非先搬移快取並更新全部連結。

## 自動檢查

- `cargo` 層（所有呼叫者）：`~/.local/bin/cargo` 連到 `tools/cargo_shared_target.py`，排在 `~/.cargo/bin` 前面。每次 cargo 都把 `CARGO_TARGET_DIR` 設成這個 repo 唯一的 target：根目錄 workspace 用 `cargo-cache.json` 登記的保留快取，否則用主工作樹同路徑的 `target/`。指向本工作樹 `target/` 子目錄的 `--target-dir` 改導到共用位置；其他獨立位置拒絕（結束碼 2）。不在 Git 裡的專案與 `cargo install` 照原樣執行。它不刪任何資料，舊的獨立副本仍要用上方盤點流程處理。
- `SessionStart`／編譯前：替已登記的新工作樹建立共用連結，不刪既有資料。
- `PreToolUse`：攔獨立快取與非登記 `--target-dir`／`CARGO_TARGET_DIR`。使用中的舊快取保留，但新編譯須指定共用位置。
- `Stop`：有新獨立副本或壞連結時不得宣告收工。
- `SessionEnd`：先寫快速盤點紀錄；只有明確啟用收工清理的 repo 才啟動背景清理。背景工作限 120 秒、使用同 repo 鎖、無自動重試，只處理先前登記略過的快取；仍在使用就保留。

證據留在共用 Git 目錄的 `cargo-cache*.json`；最近盤點在 `~/.local/state/cargo-cache/status.json`。
目前執行中的 AI 是否載入新 hook 必須另外確認，設定寫入不等於已載入。
