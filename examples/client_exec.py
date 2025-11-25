import asyncio

from ipybox.kernel.executor import ExecutionClient
from ipybox.kernel.gateway import KernelGateway
from ipybox.mcp.runner.server import ToolServer


async def main():
    async with KernelGateway():
        async with ToolServer():
            async with ExecutionClient() as client:
                result = await client.execute("print('Hello, world!')")
                print(result.text)


if __name__ == "__main__":
    asyncio.run(main())
