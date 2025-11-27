import asyncio

from ipybox.code_exec.client import KernelClient
from ipybox.code_exec.server import KernelGateway
from ipybox.tool_exec.server import ToolServer


async def main():
    async with KernelGateway():
        async with ToolServer():
            async with KernelClient() as client:
                result = await client.execute("print('Hello, world!')")
                print(result.text)


if __name__ == "__main__":
    asyncio.run(main())
