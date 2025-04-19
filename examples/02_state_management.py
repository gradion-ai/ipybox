"""
Example demonstrating state management between different client contexts.
"""

import asyncio

from ipybox import ExecutionClient, ExecutionContainer, ExecutionError


async def main():
    # --8<-- [start:usage]
    async with ExecutionContainer() as container:
        async with ExecutionClient(port=container.executor_port) as client_1:  # (1)!
            result = await client_1.execute("x = 1")  # (2)!
            assert result.text is None
            result = await client_1.execute("print(x)")  # (3)!
            assert result.text == "1"

        async with ExecutionClient(port=container.executor_port) as client_2:  # (4)!
            try:
                await client_2.execute("print(x)")  # (5)!
            except ExecutionError as e:
                assert e.args[0] == "NameError: name 'x' is not defined"


# --8<-- [end:usage]


if __name__ == "__main__":
    asyncio.run(main())
