import asyncio
import json
import sys

from ipybox.mcp_client import MCPClient

server_params_1 = {
    "command": "npx",
    "args": ["-y", "@brave/brave-search-mcp-server", "--transport", "stdio"],
    "env": {"BRAVE_API_KEY": "{BRAVE_API_KEY}"},
}


server_params_2 = {
    "url": "https://api.githubcopilot.com/mcp/",
    "headers": {"Authorization": "Bearer {GITHUB_API_KEY}"},
}


server_params_3 = {
    "command": sys.executable,
    "args": ["examples/mcp_server.py"],
}


client_1 = MCPClient(server_params=server_params_1)
client_2 = MCPClient(server_params=server_params_2)
client_3 = MCPClient(server_params=server_params_3)


async def main():
    async with client_1:
        result = await client_1.run("brave_web_search", {"query": "martin krasser", "count": 3})
        print(result)

    async with client_2:
        result = await client_2.run("list_branches", {"owner": "gradion-ai", "repo": "ipybox"})
        print(json.dumps(json.loads(result), indent=2))  # type: ignore

    async with client_3:
        result = await client_3.run("tool-1", {"s": "martin krasser"})
        print(result)


if __name__ == "__main__":
    asyncio.run(main())
