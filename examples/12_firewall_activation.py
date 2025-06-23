import asyncio

# --8<-- [start:import]
from ipybox import ExecutionClient, ExecutionContainer

# --8<-- [end:import]


async def main():
    # --8<-- [start:usage]
    CODE = """
    import socket

    try:
        with socket.create_connection(("{host}", 80), timeout=1) as s:
            print("connected")
    except Exception:
        print("timeout")
    """

    async with ExecutionContainer(tag="gradion-ai/ipybox") as container:
        async with ExecutionClient(port=container.executor_port) as client:
            result = await client.execute(CODE.format(host="example.com"))  # (1)!
            assert result.text == "connected"

            await container.init_firewall(["gradion.ai"])  # (2)!

            result = await client.execute(CODE.format(host="gradion.ai"))  # (3)!
            assert result.text == "connected"

            result = await client.execute(CODE.format(host="example.com"))  # (4)!
            assert result.text == "timeout"
    # --8<-- [end:usage]


if __name__ == "__main__":
    asyncio.run(main())
