from mcp.server.fastmcp import FastMCP


async def get_weather(city: str) -> str:
    """
    Get the weather for a city.

    Args:
        city: The city to get the weather for
    """
    return f"The weather in {city} is sunny"


def main():
    server = FastMCP("Test MCP Server")
    server.add_tool(get_weather)
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
