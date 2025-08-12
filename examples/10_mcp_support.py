import asyncio

# --8<-- [start:import]
from ipybox import ExecutionClient, ExecutionContainer, ResourceClient

# --8<-- [end:import]


async def main():
    # --8<-- [start:usage]
    server_params = {  # (1)!
        "command": "uvx",
        "args": ["mcp-server-fetch"],
    }

    async with ExecutionContainer(tag="ghcr.io/gradion-ai/ipybox") as container:
        async with ResourceClient(port=container.resource_port) as client:
            tool_names = await client.generate_mcp_sources(  # (2)!
                relpath="mcpgen",
                server_name="fetchurl",
                server_params=server_params,
            )
            assert tool_names == ["fetch"]  # (3)!

        async with ExecutionClient(port=container.executor_port) as client:
            result = await client.execute("""
                from mcpgen.fetchurl.fetch import Params, fetch
                print(fetch(Params(url="https://www.gradion.ai"))[:375])
            """)  # (4)!
            print(result.text)  # (5)!


# --8<-- [end:usage]

if __name__ == "__main__":
    asyncio.run(main())
