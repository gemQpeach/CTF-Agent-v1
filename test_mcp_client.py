import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

async def main():
    url = "http://127.0.0.1:8000/mcp"
    async with streamable_http_client(url) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool("capture_render", arguments={
                "url": "https://example.com",
                "wait_ms": 1000,
                "screenshot": False
            })
            for content in result.content:
                print(content.text[:1000])

asyncio.run(main())