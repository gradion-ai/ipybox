import asyncio
import os

from ipybox.mcp_client import MCPClient

CODE_1 = """
from mcptools.brave_search import brave_web_search as bws

result = bws.run(bws.Params(query="martin krasser", count=3))
print(result)
"""


CODE_2 = """
from mcptools.brave_search import brave_image_search as bis

result = bis.run(bis.Params(query="martin krasser", count=3))
print(result.model_dump_json(indent=2))
"""

CODE_3 = """
import os
print(os.environ["MY_VAR"])
"""


async def main():
    async with MCPClient(
        server_params={
            "command": "python",
            "args": [
                "-m",
                "ipybox.mcp_server",
                # "--workspace",
                # "/Users/martin/Development/workspace/ipybox",
                # "--sandbox",
            ],
            "env": {
                "BRAVE_API_KEY": os.getenv("BRAVE_API_KEY", ""),
                "KERNEL_ENV_MY_VAR": "my_val",
            },
        },
    ) as client:
        result = await client.run("execute_ipython_cell", {"code": CODE_1})
        print(result)
        result = await client.run("execute_ipython_cell", {"code": CODE_2})
        print(result)
        result = await client.run("execute_ipython_cell", {"code": CODE_3})
        print(result)


if __name__ == "__main__":
    asyncio.run(main())
