"""
Example demonstrating how to generate Python code for MCP tools and use them in code execution.
"""

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

    async with ExecutionContainer(tag="gradion-ai/ipybox") as container:
        async with ResourceClient(port=container.resource_port) as client:  # (2)!
            generate_result = await client.generate_mcp_sources(  # (3)!
                relpath="mcpgen",
                server_name="fetchurl",
                server_params=server_params,
            )
            assert generate_result == ["fetch"]  # (4)!

            generated_sources = await client.get_mcp_sources(  # (5)!
                relpath="mcpgen",
                server_name="fetchurl",
            )
            assert "def fetch(params: Params) -> str:" in generated_sources["fetch"]

            generated_sources = await client.get_module_sources(  # (6)!
                module_names=["mcpgen.fetchurl.fetch"],
            )
            assert "def fetch(params: Params) -> str:" in generated_sources["mcpgen.fetchurl.fetch"]

        async with ExecutionClient(port=container.executor_port) as client:
            result = await client.execute("""
                from mcpgen.fetchurl.fetch import Params, fetch
                print(fetch(Params(url="https://www.gradion.ai"))[:375])
            """)  # (7)!
            print(result.text)  # (8)!


# --8<-- [end:usage]

if __name__ == "__main__":
    asyncio.run(main())
