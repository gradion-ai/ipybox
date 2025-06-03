import asyncio

from ipybox import ExecutionClient, ExecutionContainer, ResourceClient


async def main():
    """
    Example of connecting to an external MCP server running with streamable-http transport.

    Before running this example, start the MCP server in a separate terminal:
        python tests/mcp_server.py --transport streamable-http --port 8000
    """

    # Configure server parameters for streamable-http transport
    # Note: When running inside a container, use the host machine's IP address
    # instead of localhost to connect to the external server
    server_params = {
        "type": "streamable_http",
        "url": "http://192.168.94.50:8000/mcp",  # replace with your host machine's IP address
    }

    async with ExecutionContainer(tag="gradion-ai/ipybox") as container:
        async with ResourceClient(port=container.resource_port) as client:
            # Generate Python client functions from the MCP server
            try:
                tool_names = await client.generate_mcp_sources(
                    relpath="mcpgen",
                    server_name="test_server",
                    server_params=server_params,
                )
                print(f"Generated tools: {tool_names}")
                # Should output: ['tool_1', 'tool_2']
            except Exception as e:
                print(f"Error: {e}")
                print(f"Error type: {type(e).__name__}")
                import traceback

                traceback.print_exc()

        async with ExecutionClient(port=container.executor_port) as client:
            # Import and use the generated tool
            result = await client.execute("""
                from mcpgen.test_server.tool_1 import Params, tool_1

                # Call tool-1 with a test string
                response = tool_1(Params(s="Hello from ipybox!"))
                print(response)
            """)
            print(result.text)
            # Expected output: You passed to tool 1: Hello from ipybox!


if __name__ == "__main__":
    asyncio.run(main())
