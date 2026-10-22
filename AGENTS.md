# MORTAL MCP Agent Rules

本檔是本 repo 的 AI 協作規則來源。Claude Code 讀 `CLAUDE.md`，Gemini CLI 讀 `GEMINI.md`，Cursor 讀 `.cursor/rules/mortal-mcp.mdc`，Windsurf 讀 `.windsurf/rules/mortal-mcp.md`，GitHub Copilot 讀 `.github/copilot-instructions.md`；那些檔案都只指向本檔，不另立一套規則。

## Output Style

- 面向使用者的回報預設使用繁體中文。
- 先講結果，再講原因、證據與下一步。
- 用初階工程師也看得懂的白話；陌生術語要在同一句補上意思。
- 命令、路徑、程式碼、設定名保留原文，但旁邊說明仍用白話。
- 不得把「單測通過、HTTP health、文件完成、部署完成、真機/瀏覽器驗收」混成同一種完成。

## Start Rule

- 非瑣碎工程任務先讀 `/home/cash/.agents/context-evaluation-workflow.md`、`/home/cash/.agents/skills/cash-rule/references/engineering-policy.md`，並依共用 `start-work` 檢查現況。
- 動作前先看 `git status`、目前分支、未提交/未追蹤檔、相關 process、artifacts 和 owner；不得回復不是自己造成的改動。
- repo 若有 `.codegraph/`，理解或定位程式前先用 CodeGraph；沒有索引才用 `rg`、讀檔或其他方式。不要自行替別的 repo 建索引，除非使用者明確要求。
- 重複流程或跨專案工具先讀 `.agents/skills/mortal-tools/SKILL.md`，用 `mortal_catalog` / `mortal_guide` 或既有腳本；不要重造同一套工具。

## Project Boundaries

- Read `.agents/skills/mortal-mcp/SKILL.md` before operating tools.
- Standard installable skills live under `skills/`; `.agents/skills/` is only a repo-local compatibility entry.
- The service implementation target is Rust. Legacy Python adapters may remain temporarily, but new MCP service work belongs under `src/`.
- Keep this service local to `127.0.0.1`.
- Adapters call existing project scripts; never duplicate business, game, or ledger logic.
- No arbitrary shell, SQL, file deletion, remote-host, credential, payment, or production tool entry. Fixed commands only.
- Mutations share a host lock, are bounded, and leave evidence. No automatic retries.
- Do not change, restart, or open game processes as part of MCP deployment or smoke testing unless the user explicitly asks for that operation.
- MCP health only proves the MCP server answered. It does not prove Fluke gameplay, Godot rendering, ledger correctness, or user acceptance.

## Engineering Standards

- Keep changes small and reviewable; follow existing project style before adding new abstractions.
- Prefer deterministic, bounded checks. Avoid model-driven retry loops and unbounded per-row calls.
- For DB or remote work, define batch size, stop condition, resume point, partial-failure record, and recovery path before writing.
- Secrets, tokens, `.env` files, production data, and personal credentials must not be committed or printed.
- Use structured evidence in reports: file path, command, test name, artifact, timestamp, or version. Mark unknown and unverified items plainly.
- Installation or config output is not proof that a running AI session loaded the tool; say when a restart/new session is still required.

## Validation

- For package/tooling changes, run `npm test` when relevant.
- For MCP behavior changes, run the real HTTP smoke test only when it will not restart or mutate game processes.
- For CodeGraph changes, verify `codegraph status`; if telemetry is available, turn it off for this repo.
- Final reports must list what changed, what was verified, and what remains unverified.

## 共通 Gitflow 規範

新工作遵守 [DEVELOPMENT.md](DEVELOPMENT.md)，使用 `develop` 與 `feature/`、`bug/`、`release/`、`hotfix/`。既有架構、安全、資料與驗收約束繼續有效。執行 `.repo-policy/install.py` 安裝可復原的 hooks；不得繞過失敗 gate。
