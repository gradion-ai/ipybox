import asyncio
import os

from ipybox import ExecutionClient, ExecutionContainer


async def main():
    # --8<-- [start:usage]
    HOST = "192.168.94.50"  # (1)!
    os.environ["DOCKER_HOST"] = f"tcp://{HOST}:2375"  # (2)!

    async with ExecutionContainer(tag="ghcr.io/gradion-ai/ipybox") as container:  # (3)!
        async with ExecutionClient(host=HOST, port=container.executor_port) as client:  # (4)!
            result = await client.execute("17 ** 0.13")
            print(f"Output: {result.text}")
    # --8<-- [end:usage]


if __name__ == "__main__":
    asyncio.run(main())
