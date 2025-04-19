import asyncio
import concurrent.futures
from contextlib import asynccontextmanager
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client
from mcp.types import TextContent


@asynccontextmanager
async def mcp_client(server_params: dict[str, Any]):
    if "command" in server_params:
        mgr = stdio_client(StdioServerParameters(**server_params))
    elif "url" in server_params:
        mgr = sse_client(**server_params)
    else:
        raise ValueError(f'Neither a "command" nor a "url" key in server_params: {server_params}')

    async with mgr as streams:
        yield streams


async def run_async(
    tool_name: str, params: dict[str, Any], server_params: dict[str, Any], connect_timeout: float = 5
) -> str | None:
    async with mcp_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await asyncio.wait_for(session.initialize(), timeout=connect_timeout)
            result = await session.call_tool(tool_name, arguments=params)

            match result.content:
                case [TextContent(text=text)]:
                    if result.isError:
                        raise Exception(text)
                    return text
                case _:
                    return None


def run_sync(
    tool_name: str, params: dict[str, Any], server_params: dict[str, Any], connect_timeout: float = 5
) -> str | None:
    try:
        asyncio.get_running_loop()

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(asyncio.run, run_async(tool_name, params, server_params, connect_timeout))
            return future.result()

    except RuntimeError:
        return asyncio.run(run_async(tool_name, params, server_params))
