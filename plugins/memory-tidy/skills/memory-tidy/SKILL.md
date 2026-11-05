---
name: memory-tidy
description: Use when local RAM is nearly full, "used" memory keeps growing, or the user wants idle claude/codex sessions, orphan dev servers and stale /tmp files cleaned up, or wants this cleanup scheduled. Linux, macOS, Windows (see Limits).
---

# Memory tidy

Frees memory by doing these things, in order:

1. Close claude/codex sessions that have been idle for 4 hours or more. A handoff note is written first, so the session can be resumed.
2. Stop orphan dev servers (next dev, vite, tsx watch, ts-node) whose parent is gone, with no clients, idle 2 hours or more.
3. Delete stale files under /tmp (owned by the user, unused by any process, untouched for 30 minutes or more). /tmp is scratch space, not a cache: keep work folders elsewhere (for example `~/work_space`), or list a name prefix per line in `~/.memory-tidy/tmp-keep.txt` to protect entries directly under /tmp.

4. Stop orphan MCP servers (npx/uvx/node/python commands with `mcp` in the name) whose parent is gone, idle 1 hour or more. Processes run by systemd services, ssh, databases, docker, and claude/codex themselves are never touched. Add `--keep REGEX` to protect more, or list PIDs in `~/.memory-tidy/never-kill.txt`.

5. Stop orphan claude/codex processes: command line is claude or codex, parent gone, no terminal, running 30 minutes or more (`--agent-idle-hours`), not a live interactive session. Their child processes stop with them. codex app-server is never touched. Use `--only REGEX` to limit any tidy run to matching command lines.

Docker is not touched.

## Preview first, then apply

Preview (changes nothing):

`python3 -I "${CLAUDE_PLUGIN_ROOT}/scripts/mem_tidy.py"`

Show the user what would be closed or deleted. Only after the user agrees:

`python3 -I "${CLAUDE_PLUGIN_ROOT}/scripts/mem_tidy.py" --apply`

Memory breakdown only: `python3 -I "${CLAUDE_PLUGIN_ROOT}/scripts/idle_agents.py" --report`. "Cache" is reclaimable and does not count as used.

## Schedule it (every 10 minutes)

This creates a schedule (systemd user timer on Linux, launchd agent on macOS, Task Scheduler task on Windows) that closes sessions and deletes /tmp files on its own. Ask the user first.

1. Preview: `python3 -I "${CLAUDE_PLUGIN_ROOT}/scripts/install.py"`
2. After the user agrees: `python3 -I "${CLAUDE_PLUGIN_ROOT}/scripts/install.py" --apply`
3. Options: `--min-idle-hours 4`, `--every-minutes 10`.
4. Remove: `python3 -I "${CLAUDE_PLUGIN_ROOT}/scripts/install.py" --uninstall --apply`

The installer copies the scripts to `~/.local/lib/memory-tidy/`, so the timer keeps working after the plugin updates.

## Session start reminder

`install --apply` also adds a SessionStart hook to `~/.claude/settings.json` and `~/.codex/hooks.json` (only when those folders exist; a `.bak-memory-tidy` backup is kept; `--no-hook` skips it; `--uninstall --apply` removes it). The hook runs `memory-tidy hint` (the single binary, or `python -I memory_tidy_cli.py hint`), so Claude Code and Codex both get it on Linux, macOS and Windows. It tells the AI about sessions closed earlier that may be unfinished (up to 3 from the last 3 days, current folder first, each shown once) with the resume command, and asks once a week to enable the schedule if none exists. When you see this context, mention it to the user in one or two sentences and ask whether to resume. The plugin's own `hooks/hooks.json` does the same for Claude Code and needs Python 3.

## No Python on the machine

Build outputs `memory-tidy-<platform>` come from the `memory-tidy-binaries` workflow (Actions artifacts). The single file needs no Python. Use it like this:

- `memory-tidy tidy` previews orphan MCP/dev-server cleanup; add `--apply` to act, `--tmp` for temp files.
- `memory-tidy hint` prints the start reminder (used by the hook).
- `memory-tidy install` previews the schedule and hook; add `--apply`. It copies itself to the install folder and schedules `memory-tidy tidy --apply --tmp`.
- `memory-tidy idle` closes idle sessions with handoff notes; `memory-tidy all` runs idle plus tidy (this is what the schedule runs). Add `--apply` to act.

## How idle is decided

- claude: `~/.claude/sessions/<pid>.json` has status idle and was last updated before the threshold.
- codex: the open rollout file was last modified before the threshold.
- Never closed: the session running this tool, and codex app-server.
- Skipped (shown in the preview with the reason): `kept_pid_changed` when the process start time does not match the session file (the PID was reused by something else), and `kept_busy_children` when the session has a running child that is not an MCP server (for example a build, test or dev server it started). MCP servers (command line containing `mcp`) never block closing. Docker containers are not children of the session and are not considered.

## Handoff notes

Written to `~/.local/state/idle-agents/handoffs/` before each close: first task, recent user instructions, last AI reply, git branch and uncommitted changes, and the resume command (`claude --resume <id>` or `codex resume <id>`). Nothing on disk is deleted by closing a session.

## Limits

- Linux: all four steps (idle claude/codex sessions with handoff notes, orphan dev servers, /tmp, orphan MCP servers).
- macOS and Windows: idle claude session closing with handoff notes, orphan MCP and dev servers, and temp cleanup. Idle codex closing works on macOS (uses lsof) but not on Windows (cannot find the open rollout file). No memory breakdown report outside Linux.
- The hook registration is covered by add/remove unit tests on all three platforms; a real Codex or Claude Code loading it on macOS/Windows is NOT tested. On Windows the command runs under the tool's shell (Git Bash or PowerShell).
- macOS and Windows code paths were written from the platform documentation and are NOT tested on real machines. Always run the preview first and report problems.
- A session whose long background command runs as a child is kept. A command that detached from the session (its parent is gone) is not seen as a child.
- Depends on the current claude and codex session file formats.
