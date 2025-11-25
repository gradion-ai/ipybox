import asyncio

from ipybox import ExecutionClient, ExecutionContainer


async def main():
    # --8<-- [start:run-container]
    container = ExecutionContainer(tag="ghcr.io/gradion-ai/ipybox:0.6.7")  # (1)!
    await container.run()  # (2)!
    # --8<-- [end:run-container]

    async with ExecutionClient(port=container.executor_port):
        await asyncio.sleep(1)

    # --8<-- [start:kill-container]
    await container.kill()  # (3)!
    # --8<-- [end:kill-container]


if __name__ == "__main__":
    asyncio.run(main())
