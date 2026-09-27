#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "$0")/.." && pwd)"
fluke_root="${1:?Usage: install-service.sh /absolute/Fluke/checkout}"
[[ -f "$fluke_root/scripts/fluke_preview.sh" ]] || { echo 'Fluke checkout missing' >&2; exit 1; }
uv sync --project "$repo_root" --frozen
python3 - "$repo_root" "$fluke_root" <<'PY'
import sys
from pathlib import Path
root,fluke=map(lambda s:str(Path(s).resolve()),sys.argv[1:])
# Reject systemd substitution/control syntax in paths rather than misquote it.
if any(c in root+fluke for c in '\n\r"%\\'):
    raise SystemExit('Unsupported service path characters')
p=Path.home()/'.config/systemd/user/mortal-mcp.service'
p.parent.mkdir(parents=True,exist_ok=True)
p.write_text(f'''[Unit]
Description=MORTAL local MCP tools
[Service]
Type=simple
WorkingDirectory="{root}"
Environment="MORTAL_FLUKE_ROOT={fluke}"
ExecStart="{root}/.venv/bin/python" "{root}/server.py"
Restart=no
MemoryMax=256M
CPUQuota=50%
UMask=0077
[Install]
WantedBy=default.target
''')
PY
systemctl --user daemon-reload
systemctl --user enable --now mortal-mcp.service
