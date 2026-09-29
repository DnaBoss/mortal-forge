#!/usr/bin/env python3
"""唯讀工具清單；不執行登記命令。"""
import argparse
import json
from pathlib import Path
import shutil
import sys

FIELDS = ("name", "purpose", "location", "usage", "input", "output",
          "dependencies", "risk", "verification")


def load_catalog(path):
    rows = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError("清單必須是陣列")
    names = set()
    for row in rows:
        if not isinstance(row, dict) or any(
            not isinstance(row.get(k), str) or not row[k].strip() for k in FIELDS
        ):
            raise ValueError("清單欄位缺漏或不是非空文字")
        if row["name"] in names:
            raise ValueError("程式名稱重複")
        names.add(row["name"])
        location = row["location"]
        if not (location.startswith("PATH:") and location[5:].strip()) and not Path(location).is_absolute():
            raise ValueError("位置須為絕對路徑或 PATH:指令")
    return rows


def location_exists(location):
    if location.startswith("PATH:"):
        return shutil.which(location[5:]) is not None
    return Path(location).is_file()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("keyword", nargs="?", default="")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    try:
        rows = load_catalog(Path(__file__).with_name("tools.json"))
    except (OSError, ValueError):
        print("程式清單無法讀取或格式錯誤", file=sys.stderr)
        return 2
    rows = [r for r in rows if args.keyword.casefold() in " ".join(r[k] for k in FIELDS).casefold()]
    if not rows:
        print("找不到符合的程式")
        return 1
    missing = False
    for row in rows:
        print(f"{row['name']} — {row['purpose']}\n位置：{row['location']}\n用法：{row['usage']}")
        if args.check:
            exists = location_exists(row["location"])
            missing = missing or not exists
            print("位置檢查：" + ("存在（未執行功能）" if exists else "缺失"))
    return 2 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
