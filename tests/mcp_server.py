from pathlib import Path

from mcp.server.fastmcp import FastMCP

MCP_SERVER_PATH = Path(__file__)


async def tool_1(s: str) -> str:
    """
    This is tool 1.

    Args:
        s: A string
    """
    return f"You passed to tool 1: {s}"


async def tool_2(s: str) -> str:
    """
    This is tool 2.
    """
    return f"You passed to tool 2: {s}"


def main():
    server = FastMCP("Test MCP Server")
    # This tool name is sanitized to "tool_1"
    server.add_tool(tool_1, name="tool-1")
    # This tool name remains unchanged
    server.add_tool(tool_2)
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
