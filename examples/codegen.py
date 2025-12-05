import asyncio
from pathlib import Path

# --8<-- [start:imports]
from ipybox import generate_mcp_sources

# --8<-- [end:imports]


async def generate_brave_search_wrappers():
    # --8<-- [start:gen_brave_search_wrappers]
    brave_mcp_params = {
        "command": "npx",
        "args": ["-y", "@brave/brave-search-mcp-server", "--transport", "stdio"],
        "env": {"BRAVE_API_KEY": "${BRAVE_API_KEY}"},
    }

    # Generates mcptools/brave_search/<tool_name>.py
    # modules for each tool of Brave Search MCP server
    await generate_mcp_sources(
        server_name="brave_search",
        server_params=brave_mcp_params,
        root_dir=Path("mcptools"),
    )
    # --8<-- [end:gen_brave_search_wrappers]


async def generate_github_wrappers():
    # --8<-- [start:gen_github_wrappers]
    github_mcp_params = {
        "url": "https://api.githubcopilot.com/mcp/",
        "headers": {"Authorization": "Bearer ${GITHUB_API_KEY}"},
    }

    # Generates mcptools/github/<tool_name>.py
    # modules for each tool of GitHub MCP server
    await generate_mcp_sources(
        server_name="github",
        server_params=github_mcp_params,
        root_dir=Path("mcptools"),
    )
    # --8<-- [end:gen_github_wrappers]


async def main():
    await generate_brave_search_wrappers()
    await generate_github_wrappers()


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    asyncio.run(main())
