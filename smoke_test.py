"""Real MCP round-trip; read-only, no game restart or test DB created."""
import asyncio
import json
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async def main():
    async with streamablehttp_client('http://127.0.0.1:18765/mcp') as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            names = {t.name for t in (await session.list_tools()).tools}
            assert names == {'fluke_status','fluke_open_preview','fluke_restart_preview','fluke_validate'}, names
            status = await session.call_tool('fluke_status', {})
            assert not status.isError, status
            data = json.loads(status.content[0].text)
            assert data['ok'] and 'build' in data, data
            invalid = await session.call_tool('fluke_validate', {'scenario':'not-a-scenario'})
            assert invalid.isError, invalid
            restart = await session.call_tool('fluke_restart_preview', {})
            assert 'restart_validation_pending' in restart.content[0].text
            print(json.dumps({'passed': ['discovery4','live_status','invalid_scenario_rejected','unsafe_restart_rejected'], 'status': data}, ensure_ascii=False, indent=2))

asyncio.run(main())
