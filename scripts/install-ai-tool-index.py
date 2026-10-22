#!/usr/bin/env python3
"""Install the local inventory CLI, read-only MCP and shared skill."""

import datetime
import json
import os
import subprocess
import tempfile
import tomllib
from pathlib import Path


def atomic(path, content, mode):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent)
    with os.fdopen(fd, "wb") as output:
        output.write(content)
    os.chmod(temporary, mode)
    os.replace(temporary, path)


def main():
    os.umask(0o077)
    repo = Path(__file__).resolve().parents[1]
    home = Path.home()
    common = Path(
        subprocess.check_output(
            [
                "git",
                "-C",
                str(repo),
                "rev-parse",
                "--path-format=absolute",
                "--git-common-dir",
            ],
            text=True,
        ).strip()
    ).parent
    binary = common / "target/debug/ai-tool-index-mcp"
    if not binary.is_file():
        raise SystemExit("Build ai-tool-index-mcp first")
    destination = home / ".local/lib/ai-tool-index"
    backup = (
        home
        / ".local/state/ai-tool-index/install-backup"
        / datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%SZ")
    )
    codex = home / ".codex/config.toml"
    claude = home / ".claude.json"
    original_codex = codex.read_bytes() if codex.exists() else b""
    original_claude = claude.read_bytes() if claude.exists() else b"{}"
    c = tomllib.loads(original_codex.decode())
    a = json.loads(original_claude)
    expected = str(home / ".local/bin/ai-tool-index-mcp")
    for entry in [
        c.get("mcp_servers", {}).get("ai-tool-index"),
        a.get("mcpServers", {}).get("ai-tool-index"),
    ]:
        if entry and entry.get("command") != expected:
            raise SystemExit("Existing ai-tool-index MCP differs; no settings changed")
    links = [
        home / ".agents/skills/ai-tool-index",
        home / ".codex/skills/ai-tool-index",
        home / ".claude/skills/ai-tool-index",
    ]
    for link in links:
        if (
            link.exists() or link.is_symlink()
        ) and link.resolve() != destination / "skill":
            raise SystemExit(
                "Existing ai-tool-index skill differs; no settings changed"
            )
    backup.mkdir(parents=True, exist_ok=False)
    atomic(backup / "codex.toml", original_codex, 0o600)
    atomic(backup / "claude.json", original_claude, 0o600)
    atomic(
        destination / "ai_tool_index.py",
        (repo / "tools/ai_tool_index.py").read_bytes(),
        0o700,
    )
    atomic(
        destination / "skill/SKILL.md",
        (repo / "skills/ai-tool-index/SKILL.md").read_bytes(),
        0o600,
    )
    atomic(home / ".local/bin/ai-tool-index-mcp", binary.read_bytes(), 0o700)
    atomic(
        home / ".local/bin/ai-tool-index",
        (
            '#!/bin/sh\nexec /usr/bin/python3 "'
            + str(destination / "ai_tool_index.py")
            + '" "$@"\n'
        ).encode(),
        0o700,
    )
    for link in links:
        link.parent.mkdir(parents=True, exist_ok=True)
        if not link.is_symlink():
            link.symlink_to(destination / "skill")
    if (codex.read_bytes() if codex.exists() else b"") != original_codex or (
        claude.read_bytes() if claude.exists() else b"{}"
    ) != original_claude:
        raise SystemExit(
            "Agent settings changed during installation; settings not overwritten"
        )
    if "ai-tool-index" not in c.get("mcp_servers", {}):
        new = (
            original_codex
            + (
                "\n[mcp_servers.ai-tool-index]\ncommand = "
                + json.dumps(expected)
                + "\nstartup_timeout_sec = 10\n"
            ).encode()
        )
        tomllib.loads(new.decode())
        atomic(codex, new, 0o600)
    a.setdefault("mcpServers", {})["ai-tool-index"] = {
        "type": "stdio",
        "command": expected,
        "args": [],
    }
    atomic(claude, (json.dumps(a, ensure_ascii=False, indent=2) + "\n").encode(), 0o600)
    print(
        json.dumps(
            {
                "installed": True,
                "backup": str(backup),
                "cli": str(home / ".local/bin/ai-tool-index"),
                "new_session_required": True,
            }
        )
    )


if __name__ == "__main__":
    main()
