import argparse
import json
import subprocess
import sys
from pathlib import Path

AUDIT = Path(__file__).with_name("worktree_idle_audit.py")


def main():
    p = argparse.ArgumentParser(description="Remove idle SAFE git worktrees of the given repos; dry-run unless --apply")
    p.add_argument("--repo", action="append", required=True)
    p.add_argument("--days", type=float, default=5)
    p.add_argument("--apply", action="store_true")
    a = p.parse_args()
    for repo in a.repo:
        out = subprocess.run([sys.executable, str(AUDIT), "--repo", repo, "--days", str(a.days), "--json"],
                             capture_output=True, text=True, check=True).stdout
        for row in json.loads(out)["rows"]:
            if row["verdict"] not in ("SAFE", "PRUNABLE"):
                print(f"keep {row['path']} {row['verdict']}")
                continue
            if not a.apply:
                print(f"would remove {row['path']}")
                continue
            if row["verdict"] == "SAFE":
                r = subprocess.run(["git", "-C", repo, "worktree", "remove", row["path"]], capture_output=True, text=True)
                print(f"removed {row['path']}" if r.returncode == 0 else f"failed {row['path']}: {r.stderr.strip()}")
        if a.apply:
            subprocess.run(["git", "-C", repo, "worktree", "prune"], check=True)


main()
