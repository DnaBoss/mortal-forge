"""CLI bridge for sessions without a dynamically registered MCP connector."""
import argparse
import asyncio
import json
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('tool')
    parser.add_argument('--arguments', default='{}', help='JSON object, not shell commands')
    args = parser.parse_args()
    async with streamablehttp_client('http://127.0.0.1:18765/mcp') as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(args.tool, json.loads(args.arguments))
            print(result.model_dump_json(indent=2))
            if result.isError:
                raise SystemExit(1)
            if result.content and result.content[0].type == 'text':
                try:
                    payload = json.loads(result.content[0].text)
                except ValueError:
                    return
                if isinstance(payload, dict) and payload.get('ok') is False:
                    raise SystemExit(1)

if __name__ == '__main__':
    asyncio.run(main())
