import asyncio

from ipybox.mcp_client import MCPClient

CODE = """
import matplotlib.pyplot as plt

plt.plot([1, 2, 3], [4, 5, 6])
plt.show()
"""


async def main():
    async with MCPClient(
        server_params={
            "command": "python",
            "args": [
                "-m",
                "ipybox.mcp_server",
            ],
        },
    ) as client:
        result = await client.run("execute_ipython_cell", {"code": CODE})
        print(result)


if __name__ == "__main__":
    asyncio.run(main())
