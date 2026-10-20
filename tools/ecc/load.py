#!/usr/bin/env python3
"""Read pinned ECC references; execute no upstream code."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

MANIFEST = Path(__file__).with_name("manifest.json")
POLICY = Path(__file__).with_name("local-policy.md")


def verified(manifest, group=None):
    root = Path(manifest["source_root"]).resolve()
    actual = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True, timeout=10
    ).strip()
    if actual != manifest["commit"]:
        raise ValueError("ECC checkout version differs from pinned manifest")
    paths = manifest["groups"][group] if group else manifest["files"]
    contents = []
    for rel in paths:
        path = (root / rel).resolve()
        if not path.is_relative_to(root):
            raise ValueError("ECC reference escapes source root")
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != manifest["files"][rel]:
            raise ValueError(f"ECC reference changed: {rel}")
        if group:
            contents.append((rel, data.decode("utf-8")))
    return contents


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("group", nargs="?")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    try:
        manifest = json.loads(MANIFEST.read_text())
        if args.verify:
            verified(manifest)
            print(json.dumps({"commit": manifest["commit"], "verified_files": len(manifest["files"])}))
            return 0
        if args.group not in manifest["groups"]:
            parser.error("Choose one of: " + ", ".join(manifest["groups"]))
        contents = verified(manifest, args.group)
        print(POLICY.read_text())
        print("\nECC reference version: " + manifest["commit"])
        for rel, text in contents:
            print(f"\n--- Reference: {rel} ---\n{text}")
        print("\n以上為上游參考；任務授權、專案規則及開頭的本機限制優先。")
        return 0
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        print(f"ecc-load: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
