"""
Example demonstrating how to install dependencies at runtime.
"""

import asyncio

from ipybox import ExecutionClient, ExecutionContainer


async def main():
    # --8<-- [start:usage]
    async with ExecutionContainer() as container:
        async with ExecutionClient(port=container.executor_port) as client:
            execution = await client.submit("!pip install einops")  # (1)!
            async for chunk in execution.stream():  # (2)!
                print(chunk, end="", flush=True)

            result = await client.execute("""
                import einops
                print(einops.__version__)
            """)  # (3)!
            print(f"Output: {result.text}")  # (4)!
    # --8<-- [end:usage]


if __name__ == "__main__":
    asyncio.run(main())
