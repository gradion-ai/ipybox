import asyncio

# --8<-- [start:import]
from ipybox import ExecutionClient, ExecutionContainer, ResourceClient

# --8<-- [end:import]


async def main():
    # --8<-- [start:usage]
    server_params = {  # (1)!
        "type": "streamable_http",
        "url": "http://[YOUR-HOST-IP-ADDRESS]:8000/mcp",
    }

    async with ExecutionContainer(tag="gradion-ai/ipybox") as container:
        async with ResourceClient(port=container.resource_port) as client:
            tool_names = await client.generate_mcp_sources(  # (2)!
                relpath="mcpgen",
                server_name="test_server",
                server_params=server_params,
            )
            assert tool_names == ["tool_1", "tool_2"]  # (3)!

        async with ExecutionClient(port=container.executor_port) as client:
            result = await client.execute("""
                from mcpgen.test_server.tool_1 import Params, tool_1
                response = tool_1(Params(s="Hello from ipybox!"))
                print(response)
            """)  # (4)!
            print(result.text)  # (5)!


# --8<-- [end:usage]

if __name__ == "__main__":
    asyncio.run(main())
