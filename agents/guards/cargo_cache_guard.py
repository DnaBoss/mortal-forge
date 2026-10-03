#!/usr/bin/env python3
"""Installed hook entry; reusable implementation stays in mortal-mcp/tools."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from cargo_cache import hook

if __name__ == '__main__':
    print(json.dumps(hook(json.loads(sys.stdin.read(100000))), ensure_ascii=False))
