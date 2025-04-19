"""
Basic usage example demonstrating how to execute Python code in an execution container.
"""

import asyncio

# --8<-- [start:import]
from ipybox import ExecutionClient, ExecutionContainer

# --8<-- [end:import]


async def main():
    # --8<-- [start:usage]
    async with ExecutionContainer(tag="gradion-ai/ipybox") as container:  # (1)!
        async with ExecutionClient(port=container.executor_port) as client:  # (2)!
            result = await client.execute("print('Hello, world!')")  # (3)!
            print(f"Output: {result.text}")  # (4)!


# --8<-- [end:usage]

if __name__ == "__main__":
    asyncio.run(main())
