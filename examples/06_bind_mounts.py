"""
Example demonstrating how to use bind mounts to access host files.
"""

import asyncio

import aiofiles
import aiofiles.os

from ipybox import ExecutionClient, ExecutionContainer


async def main():
    # --8<-- [start:usage]
    await aiofiles.os.makedirs("data", exist_ok=True)
    await aiofiles.os.makedirs("output", exist_ok=True)

    binds = {  # (1)!
        "./data": "data",  # (2)!
        "./output": "output",  # (3)!
    }

    async with aiofiles.open("data/input.txt", "w") as f:
        await f.write("hello world")

    async with ExecutionContainer(binds=binds) as container:
        async with ExecutionClient(port=container.executor_port) as client:
            await client.execute("""
                with open('data/input.txt') as f:
                    data = f.read()

                processed = data.upper()

                with open('output/result.txt', 'w') as f:
                    f.write(processed)
            """)  # (4)!

    async with aiofiles.open("output/result.txt", "r") as f:  # (5)!
        result = await f.read()
        assert result == "HELLO WORLD"
    # --8<-- [end:usage]


if __name__ == "__main__":
    asyncio.run(main())
