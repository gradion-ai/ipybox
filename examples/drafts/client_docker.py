import asyncio
from pathlib import Path

from ipybox.mcp_client import MCPClient

PROJECT_DIR = Path(__file__).parent.parent


CODE_2 = """
from mcptools.brave_search import brave_image_search as bis

result = bis.run(bis.Params(query="martin krasser", count=3))
print(result.model_dump_json(indent=2))
"""


async def main():
    async with MCPClient(
        server_params={
            "command": "docker",
            "args": [
                "run",
                "-i",
                "--rm",
                "-v",
                f"{PROJECT_DIR}:/app/workspace",
                "ipybox",
            ],
        },
    ) as client:
        result = await client.run("execute_ipython_cell", {"code": CODE_2})
        print(result)


if __name__ == "__main__":
    asyncio.run(main())
