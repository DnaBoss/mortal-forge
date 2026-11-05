---
name: memory-tidy
description: Use when local RAM is nearly full, "used" memory keeps growing, or the user wants idle claude/codex sessions, orphan dev servers and stale /tmp files cleaned up, or wants this cleanup scheduled. Linux, macOS, Windows (see Limits).
---

# Memory tidy

Frees memory by doing these things, in order:

1. Close claude/codex sessions that have been idle for 4 hours or more. A handoff note is written first, so the session can be resumed.
2. Stop orphan dev servers (next dev, vite, tsx watch, ts-node) whose parent is gone, with no clients, idle 2 hours or more.
3. Delete stale files under /tmp (owned by the user, unused by any process, untouched for 6 hours or more).

4. Stop orphan MCP servers (npx/uvx/node/python commands with `mcp` in the name) whose parent is gone, idle 1 hour or more. Processes run by systemd services, ssh, databases, docker, and claude/codex themselves are never touched. Add `--keep REGEX` to protect more, or list PIDs in `~/.memory-tidy/never-kill.txt`.

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

## How idle is decided

- claude: `~/.claude/sessions/<pid>.json` has status idle and was last updated before the threshold.
- codex: the open rollout file was last modified before the threshold.
- Never closed: the session running this tool, and codex app-server.

## Handoff notes

Written to `~/.local/state/idle-agents/handoffs/` before each close: first task, recent user instructions, last AI reply, git branch and uncommitted changes, and the resume command (`claude --resume <id>` or `codex resume <id>`). Nothing on disk is deleted by closing a session.

## Limits

- Linux: all four steps (idle claude/codex sessions with handoff notes, orphan dev servers, /tmp, orphan MCP servers).
- macOS and Windows: only `tidy_any.py` (orphan MCP and dev servers, optional `--tmp` temp cleanup). Idle claude/codex session closing needs /proc and is Linux only.
- macOS and Windows code paths were written from the platform documentation and are NOT tested on real machines. Always run the preview first and report problems.
- A claude session running a long background command but showing idle can be closed on Linux. Check the preview before applying.
- Depends on the current claude and codex session file formats.
