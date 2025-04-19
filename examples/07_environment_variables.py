"""
Example demonstrating how to use environment variables in the execution container.
"""

import asyncio

from ipybox import ExecutionClient, ExecutionContainer


async def main():
    # --8<-- [start:usage]
    # Define environment variables for the container
    env = {"API_KEY": "secret-key-123", "DEBUG": "1"}  # (1)!

    async with ExecutionContainer(env=env) as container:
        async with ExecutionClient(port=container.executor_port) as client:
            result = await client.execute("""
                import os

                api_key = os.environ['API_KEY']
                print(f"Using API key: {api_key}")

                debug = bool(int(os.environ.get('DEBUG', '0')))
                if debug:
                    print("Debug mode enabled")
            """)  # (2)!
            print(result.text)  # (3)!
    # --8<-- [end:usage]


if __name__ == "__main__":
    asyncio.run(main())
