#!/usr/bin/env python3
"""Count empty-looking Taiwan futures minute bars in Helios serving storage.

This is one read-only PostgreSQL batch. It does not manufacture expected bars,
infer missing trading minutes, inspect ticks, or modify permanent database rows.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from typing import Callable


STATEMENT_TIMEOUT_MS = 120_000
PROCESS_TIMEOUT_SECONDS = 150

SQL = r"""
BEGIN READ ONLY;
SET LOCAL lock_timeout = '2s';
SET LOCAL statement_timeout = '120s';
SET LOCAL max_parallel_workers_per_gather = 0;
SELECT COALESCE(
    json_agg(row_to_json(summary) ORDER BY summary.symbol, summary.session,
             summary.quality_status)::text,
    '[]'
)
FROM (
    SELECT symbol, session, quality_status,
           count(*)::bigint AS bars,
           count(*) FILTER (WHERE volume = 0)::bigint AS zero_volume,
           count(*) FILTER (WHERE volume IS NULL)::bigint AS null_volume,
           count(*) FILTER (
               WHERE open IS NULL OR high IS NULL OR low IS NULL OR close IS NULL
           )::bigint AS bars_with_missing_ohlc,
           count(*) FILTER (
               WHERE open = 0 AND high = 0 AND low = 0 AND close = 0
           )::bigint AS all_zero_ohlc,
           count(*) FILTER (
               WHERE volume = 0 AND
                     (open IS NULL OR high IS NULL OR low IS NULL OR close IS NULL)
           )::bigint AS zero_volume_and_missing_ohlc,
           min(bar_end_ts) FILTER (WHERE volume = 0) AS first_zero_volume_bar,
           max(bar_end_ts) FILTER (WHERE volume = 0) AS last_zero_volume_bar
    FROM mkt_1m
    WHERE symbol IN ('TXF', 'MTX', 'MXF')
    GROUP BY symbol, session, quality_status
) AS summary;
COMMIT;
"""


@dataclass(frozen=True)
class Result:
    stdout: bytes
    stderr: bytes
    returncode: int


def run_once(
    *,
    runner: Callable[..., subprocess.CompletedProcess[bytes]] = subprocess.run,
) -> Result:
    """Run one fixed SQL batch; return failures without retrying."""
    command = [
        "docker", "exec", "-i", "helios-postgres", "psql", "-X", "-q", "-A", "-t",
        "-v", "ON_ERROR_STOP=1", "-U", "helios", "-d", "helios",
    ]
    try:
        completed = runner(
            command,
            input=SQL.encode("utf-8"),
            capture_output=True,
            timeout=PROCESS_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return Result(b"", b"Database scan timed out; stopped without retry.\n", 124)
    except OSError as exc:
        return Result(b"", f"Could not start database scan: {exc}\n".encode(), 2)
    return Result(completed.stdout, completed.stderr, completed.returncode)


def main() -> int:
    result = run_once()
    if result.stdout:
        sys.stdout.buffer.write(result.stdout)
    if result.stderr:
        sys.stderr.buffer.write(result.stderr)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
