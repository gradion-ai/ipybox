import asyncio

from ipybox import ExecutionClient, ExecutionContainer


async def main():
    # --8<-- [start:usage]
    env = {"API_KEY": "secret-key-123", "DEBUG": "1"}

    async with ExecutionContainer(tag="ghcr.io/gradion-ai/ipybox:0.6.7", env=env) as container:  # (1)!
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
