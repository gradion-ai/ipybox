"""
Example demonstrating output streaming during code execution.
"""

import asyncio

from ipybox import ExecutionClient, ExecutionContainer


async def main():
    # --8<-- [start:usage]
    async with ExecutionContainer() as container:
        async with ExecutionClient(port=container.executor_port) as client:
            code = """
            import time
            for i in range(5):
                print(f"Processing step {i}")
                time.sleep(1)
            """  # (1)!

            execution = await client.submit(code)  # (2)!
            print("Streaming output:")
            async for chunk in execution.stream():  # (3)!
                print(f"Received output: {chunk.strip()}")  # (4)!

            result = await execution.result()  # (5)!
            print("\nAggregated output:")
            print(result.text)  # (6)!
    # --8<-- [end:usage]


if __name__ == "__main__":
    asyncio.run(main())
