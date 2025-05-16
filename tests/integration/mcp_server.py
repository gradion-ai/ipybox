from mcp.server.fastmcp import FastMCP


async def tool_1(s: str) -> str:
    """
    This is tool 1.

    Args:
        s: A string
    """
    return f"You passed to tool 1: {s}"


def main():
    server = FastMCP("Test MCP Server")
    server.add_tool(tool_1)
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
