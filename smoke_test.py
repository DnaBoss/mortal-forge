"""Real MCP round-trip; read-only, no game restart or test DB created."""
import asyncio
import json
import fcntl
import os
import tempfile
from pathlib import Path
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async def main():
    async with streamablehttp_client('http://127.0.0.1:18765/mcp') as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            names = {t.name for t in (await session.list_tools()).tools}
            assert names == {'fluke_status','fluke_open_preview','fluke_restart_preview','fluke_validate','fluke_audit_continuity'}, names
            status = await session.call_tool('fluke_status', {})
            assert not status.isError, status
            data = json.loads(status.content[0].text)
            assert data['ok'] and 'build' in data, data
            invalid = await session.call_tool('fluke_validate', {'scenario':'not-a-scenario'})
            assert invalid.isError, invalid
            with open(Path(tempfile.gettempdir()) / f"fluke-operations-{os.getuid()}.lock", "a") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                busy = await session.call_tool('fluke_open_preview', {})
                assert 'operation_in_progress' in busy.content[0].text
            print(json.dumps({'passed': ['discovery5','live_status','invalid_scenario_rejected','concurrent_operation_rejected'], 'status': data}, ensure_ascii=False, indent=2))

asyncio.run(main())
