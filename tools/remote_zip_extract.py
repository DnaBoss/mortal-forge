#!/usr/bin/env python3
"""Extract selected members from a remote zip over HTTP Range requests.

Downloads only the central directory and the chosen members, not the whole
archive. Useful for large bundles such as Godot export templates (.tpz).

Usage:
  remote_zip_extract.py URL --list [--match SUBSTR]
  remote_zip_extract.py URL --out DIR --match SUBSTR [--match SUBSTR ...]

Exit codes: 0 ok, 2 bad input / server lacks Range support / no match.
"""
import argparse
import io
import os
import sys
import urllib.request
import zipfile

TIMEOUT_S = 60
MAX_MEMBER_BYTES = 200 * 1024 * 1024


class RangeFile(io.RawIOBase):
    def __init__(self, url: str):
        self.url = url
        self.pos = 0
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            self.url = resp.geturl()
            self.size = int(resp.headers["Content-Length"])
            if resp.headers.get("Accept-Ranges", "").lower() != "bytes":
                raise SystemExit("server does not advertise byte ranges")
        self.fetched = 0

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=io.SEEK_SET):
        base = {io.SEEK_SET: 0, io.SEEK_CUR: self.pos, io.SEEK_END: self.size}[whence]
        self.pos = max(0, base + offset)
        return self.pos

    def readinto(self, b):
        data = self._fetch(len(b))
        b[: len(data)] = data
        return len(data)

    def _fetch(self, n):
        if self.pos >= self.size:
            return b""
        end = self.size - 1 if n is None or n < 0 else min(self.size, self.pos + n) - 1
        req = urllib.request.Request(self.url, headers={"Range": f"bytes={self.pos}-{end}"})
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            if resp.status != 206:
                raise SystemExit(f"expected 206 partial content, got {resp.status}")
            data = resp.read()
        self.pos += len(data)
        self.fetched += len(data)
        return data


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--match", action="append", default=[])
    ap.add_argument("--out")
    args = ap.parse_args()
    if not args.url.startswith("https://"):
        print("only https URLs are accepted", file=sys.stderr)
        return 2
    rf = RangeFile(args.url)
    zf = zipfile.ZipFile(io.BufferedReader(rf, buffer_size=1 << 20))
    names = [i for i in zf.infolist() if not args.match or any(m in i.filename for m in args.match)]
    if args.list:
        for info in names:
            print(f"{info.file_size:>12} {info.filename}")
        print(f"fetched_bytes={rf.fetched} archive_bytes={rf.size}", file=sys.stderr)
        return 0
    if not args.out or not args.match or not names:
        print("need --out and --match that selects at least one member", file=sys.stderr)
        return 2
    os.makedirs(args.out, exist_ok=True)
    for info in names:
        if info.file_size > MAX_MEMBER_BYTES:
            print(f"skip oversized {info.filename}", file=sys.stderr)
            continue
        target = os.path.join(args.out, os.path.basename(info.filename))
        with zf.open(info) as src, open(target, "wb") as dst:
            dst.write(src.read())
        print(f"{info.file_size:>12} {target}")
    print(f"fetched_bytes={rf.fetched} archive_bytes={rf.size}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
