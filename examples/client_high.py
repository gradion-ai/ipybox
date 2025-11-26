import asyncio
import os

from ipybox.mcp_tools.runner.client import ToolRunner
from ipybox.mcp_tools.runner.server import ToolServer
from ipybox.utils import arun

server_params_1 = {
    "command": "npx",
    "args": ["-y", "@brave/brave-search-mcp-server", "--transport", "stdio"],
    "env": {"BRAVE_API_KEY": os.getenv("BRAVE_API_KEY")},
}


server_params_2 = {
    "command": "python",
    "args": ["examples/mcp_server.py"],
}


async def main_1():
    async with ToolServer():
        client = ToolRunner(
            server_name="test",
            server_params=server_params_1,
        )

        result = await client.run("brave_web_search", {"query": "martin krasser", "count": 3})
        print(result)

        # result = await client.run("tool-1", {"s": "hello"})
        # print(result)


async def main_2():
    async with ToolServer():
        client = ToolRunner(
            server_name="test",
            server_params=server_params_2,
        )
        result = await arun(client.run_sync, "tool-1", {"s": "hello"})
        print(result)


if __name__ == "__main__":
    asyncio.run(main_1())
    asyncio.run(main_2())
