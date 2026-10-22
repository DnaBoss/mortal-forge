#!/usr/bin/env python3
"""Read-only cash-rule compliance report: the three numbers enforcement is judged by.

  1. `*.checkpoints.jsonl` invalid rate across repos (files deduplicated by content hash);
  2. finish_check Stop-hook: blocks, gave_up count, and how many blocks were followed
     by a passing stop in the same repo (fixed-after-block rate);
  3. lessons.md: entry titles that look alike (the same mistake recorded twice).

Run: ~/tools/cash-rule-compliance [--roots DIR ...] [--days 7] [--json]
Targets: invalid rate 0, fixed-after-block 100%, look-alike pairs 0.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
from pathlib import Path

SKILL_SCRIPTS = Path.home() / ".claude/skills/cash-rule/scripts"
FINISH_LOG = Path.home() / ".local/state/agent-guards/finish_check.jsonl"
LESSONS = Path.home() / ".agents/lessons.md"
SKIP_DIRS = {"node_modules", "target", "venv", "dist", "build", "__pycache__"}
TITLE = re.compile(r"^(?:## \d{4}-\d{2}-\d{2} |\d+\. \*\*)(.+?)\**\s*$", re.M)


def checkpoint_files(roots):
    seen, out = set(), []
    for root in roots:
        for d, dirs, files in os.walk(root):
            dirs[:] = [x for x in dirs if x not in SKIP_DIRS and not x.startswith(".")]
            for f in files:
                if f.endswith(".checkpoints.jsonl"):
                    path = Path(d, f)
                    digest = hashlib.sha256(path.read_bytes()).hexdigest()
                    if digest not in seen:
                        seen.add(digest)
                        out.append(path)
    return out


def checkpoint_report(roots):
    sys.path.insert(0, str(SKILL_SCRIPTS))
    from validate_checkpoints import read_records, validate_records
    invalid = []
    files = checkpoint_files(roots)
    for path in files:
        try:
            errors = validate_records(read_records(path))
        except (OSError, ValueError):
            errors = ["unreadable"]
        if errors:
            invalid.append(str(path))
    return {"unique_files": len(files), "invalid": len(invalid),
            "invalid_rate": round(len(invalid) / len(files), 3) if files else None, "invalid_paths": invalid}


def finish_report(days):
    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    rows = []
    if FINISH_LOG.exists():
        for line in FINISH_LOG.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
                at = dt.datetime.strptime(row["at"], "%Y-%m-%dT%H:%M:%S%z")
            except (ValueError, KeyError):
                continue
            if at >= since:
                rows.append(row)
    # Rows written before 2026-10-02 have no `cwd`, so "fixed later" cannot be assessed for them.
    legacy = sum(1 for r in rows if "cwd" not in r and r.get("problems") and not r.get("second_stop"))
    blocks = [i for i, r in enumerate(rows) if "cwd" in r and r.get("blocked")]
    fixed = sum(1 for i in blocks if any(r.get("cwd") == rows[i]["cwd"] and not r.get("problems") for r in rows[i + 1:]))
    return {"stops": len(rows), "blocks": len(blocks), "legacy_blocks_unassessable": legacy,
            "gave_up": sum(1 for r in rows if r.get("gave_up")),
            "fixed_after_block": fixed, "fixed_rate": round(fixed / len(blocks), 3) if blocks else None}


PROJECT_NOISE = re.compile(r"jobresearch|fluke|helios|aletheia|ai-mall|aimall|crossec|newretail|orca|#\d+|\bv\d+", re.I)


def bigrams(text):
    """Character bigrams of a title with project names and punctuation removed."""
    text = re.sub(r"[\s`*（）()「」,，。：:；;／/#\-—]", "", PROJECT_NOISE.sub("", text.lower()))
    return {text[i:i + 2] for i in range(len(text) - 1)}


def lessons_report(threshold=0.5):
    """Overlap coefficient (shared / smaller set) on title bigrams; 0.5 matched the five known repeats on 2026-10-02."""
    if not LESSONS.exists():
        return {"entries": 0, "lookalike_pairs": []}
    titles = TITLE.findall(LESSONS.read_text(encoding="utf-8"))
    grams = [bigrams(t) for t in titles]
    pairs = []
    for i in range(len(titles)):
        for j in range(i + 1, len(titles)):
            if not grams[i] or not grams[j]:
                continue
            score = len(grams[i] & grams[j]) / min(len(grams[i]), len(grams[j]))
            if score >= threshold:
                pairs.append({"a": titles[i], "b": titles[j], "similarity": round(score, 2)})
    guarded = LESSONS.read_text(encoding="utf-8").count("guard:")
    return {"entries": len(titles), "guard_tags": guarded, "lookalike_pairs": pairs}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--roots", nargs="+", default=[str(Path.home() / "work_space")])
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = {"generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
              "checkpoints": checkpoint_report(args.roots), "finish_check": finish_report(args.days),
              "lessons": lessons_report()}
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    c, f, l = report["checkpoints"], report["finish_check"], report["lessons"]
    print(f"進度紀錄：{c['unique_files']} 份，不合格 {c['invalid']}（比率 {c['invalid_rate']}，目標 0）")
    for p in c["invalid_paths"]:
        print(f"  - {p}")
    print(f"收工檢查（近 {args.days} 天）：stop {f['stops']} 次、擋下 {f['blocks']} 次、放棄 {f['gave_up']} 次、"
          f"擋下後修好 {f['fixed_after_block']}（比率 {f['fixed_rate']}，目標 1.0）；"
          f"舊格式紀錄擋下 {f['legacy_blocks_unassessable']} 次無法判斷是否修好")
    print(f"錯誤知識庫：{l['entries']} 條、已標 guard {l['guard_tags']} 條、疑似重複 {len(l['lookalike_pairs'])} 組（目標 0）")
    for pair in l["lookalike_pairs"]:
        print(f"  - {pair['similarity']}：{pair['a']} ⟷ {pair['b']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
