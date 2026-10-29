#!/usr/bin/env bash
set -eu
if [ "${DRY:-0}" = 1 ]; then
  exec /usr/bin/python3 "$HOME/tools/memory_manager/manager.py" --dry-run
fi
exec /usr/bin/python3 "$HOME/tools/memory_manager/manager.py" "$@"
