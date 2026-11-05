---
name: memory-tidy
description: Use when local RAM is nearly full, "used" memory keeps growing, or the user wants idle claude/codex sessions, orphan dev servers and stale /tmp files cleaned up, or wants this cleanup scheduled. Linux only.
---

# Memory tidy

Frees memory on Linux by doing three things, in order:

1. Close claude/codex sessions that have been idle for 4 hours or more. A handoff note is written first, so the session can be resumed.
2. Stop orphan dev servers (next dev, vite, tsx watch, ts-node) whose parent is gone, with no clients, idle 2 hours or more.
3. Delete stale files under /tmp (owned by the user, unused by any process, untouched for 6 hours or more).

Docker is not touched.

## Preview first, then apply

Preview (changes nothing):

`python3 -I "${CLAUDE_PLUGIN_ROOT}/scripts/mem_tidy.py"`

Show the user what would be closed or deleted. Only after the user agrees:

`python3 -I "${CLAUDE_PLUGIN_ROOT}/scripts/mem_tidy.py" --apply`

Memory breakdown only: `python3 -I "${CLAUDE_PLUGIN_ROOT}/scripts/idle_agents.py" --report`. "Cache" is reclaimable and does not count as used.

## Schedule it (every 10 minutes)

This creates a systemd user timer that closes sessions and deletes /tmp files on its own. Ask the user first.

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

- Linux with /proc and systemd user sessions only. No macOS or Windows support.
- A claude session that is running a long background command but shows idle can be closed. Check the preview before applying.
- Depends on the current claude and codex session file formats.
