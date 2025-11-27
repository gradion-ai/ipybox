import asyncio
from pathlib import Path

from ipybox.mcp_apigen import generate_mcp_sources


async def main():
    server_params_1 = {
        "command": "uvx",
        "args": ["mcp-server-fetch"],
    }

    server_params_2 = {
        "command": "npx",
        "args": ["-y", "@brave/brave-search-mcp-server", "--transport", "stdio"],
        "env": {"BRAVE_API_KEY": "{BRAVE_API_KEY}"},
    }

    server_params_3 = {
        "command": "uvx",
        "args": ["--quiet", "pubmedmcp@0.1.3"],
        "env": {"UV_PYTHON": "3.12"},
    }

    server_params_4 = {
        "url": "https://api.githubcopilot.com/mcp/",
        "headers": {"Authorization": "Bearer {GITHUB_API_KEY}"},
    }

    server_params_5 = {
        "command": "python",
        "args": ["-m", "examples.mcp_server"],
    }

    root_dir = Path("mcptools")

    await generate_mcp_sources("fetch", server_params_1, root_dir)
    await generate_mcp_sources("brave_search", server_params_2, root_dir)
    await generate_mcp_sources("pubmed", server_params_3, root_dir)
    await generate_mcp_sources("github", server_params_4, root_dir)
    await generate_mcp_sources("test", server_params_5, root_dir)


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    asyncio.run(main())
