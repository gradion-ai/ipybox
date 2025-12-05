import asyncio

from ipybox.kernel_mgr.client import KernelClient
from ipybox.kernel_mgr.server import KernelGateway
from ipybox.tool_exec.server import ToolServer

CODE = """
from mcptools.fetch import fetch

result = fetch.run(fetch.Params(url="https://gradion.ai"))
print(result)
"""


async def main():
    async with ToolServer():
        async with KernelGateway():
            async with KernelClient() as client:
                result = await client.execute(CODE)
                print(result.text)


if __name__ == "__main__":
    asyncio.run(main())
