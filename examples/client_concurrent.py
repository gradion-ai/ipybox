import asyncio

from ipybox.mcp_client import MCPClient

server_params = {
    "command": "python",
    "args": ["examples/mcp_server.py"],
}


async def main():
    client_1 = MCPClient(server_params=server_params)

    async with client_1:
        coros = [client_1.run("tool_2", {"s": f"hello {i}", "delay": i}) for i in range(4)]
        for future in asyncio.as_completed(coros):
            print(await future)


if __name__ == "__main__":
    asyncio.run(main())
