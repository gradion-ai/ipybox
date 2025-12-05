import asyncio

from ipybox.mcp_client import MCPClient

server_params_1 = {
    "command": "uvx",
    "args": ["mcp-server-fetch"],
}

server_params_2 = {
    "command": "npx",
    "args": ["-y", "@brave/brave-search-mcp-server", "--transport", "stdio"],
    "env": {"BRAVE_API_KEY": "{BRAVE_API_KEY}"},
}


async def main():
    async with MCPClient(server_params={"command": "python", "args": ["-m", "ipybox.mcp_server"]}) as client:
        result = await client.run(
            tool_name="register_mcp_server",
            tool_args={
                "server_name": "fetch",
                "server_params": server_params_1,
            },
        )
        print(result)
        result = await client.run(
            tool_name="register_mcp_server",
            tool_args={
                "server_name": "brave_search",
                "server_params": server_params_2,
            },
        )
        print(result)


if __name__ == "__main__":
    asyncio.run(main())
