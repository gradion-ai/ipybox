import asyncio
from pathlib import Path

from ipybox import ApprovalRequest, CodeExecutionResult, CodeExecutor, generate_mcp_sources

SERVER_PARAMS = {
    "command": "npx",
    "args": ["-y", "@brave/brave-search-mcp-server", "--transport", "stdio"],
    "env": {"BRAVE_API_KEY": "${BRAVE_API_KEY}"},
}

CODE = """
from mcptools.brave_search import brave_image_search

result = brave_image_search.run(brave_image_search.Params(query="robo cats", count=5))

for image in result.items:
    print(f"- [{image.title}]({image.properties.url})")
"""


async def main():
    await generate_mcp_sources("brave_search", SERVER_PARAMS, Path("mcptools"))

    async with CodeExecutor() as executor:
        async for item in executor.stream(CODE):
            match item:
                case ApprovalRequest():
                    await item.accept()
                case CodeExecutionResult():
                    print(item.text)


if __name__ == "__main__":
    asyncio.run(main())
