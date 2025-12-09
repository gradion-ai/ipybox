import asyncio
from pathlib import Path

from ipybox import ApprovalRequest, CodeExecutionResult, CodeExecutor, generate_mcp_sources
from ipybox.utils import arun

SERVER_PARAMS = {
    "command": "npx",
    "args": [
        "-y",
        "@brave/brave-search-mcp-server",
        "--transport",
        "stdio",
    ],
    "env": {
        "BRAVE_API_KEY": "${BRAVE_API_KEY}",
    },
}

CODE = """
from mcptools.brave_search.brave_image_search import Params, Result, run

result: Result = run(Params(query="neural topic models", count=3))

for image in result.items:
    print(f"- [{image.title}]({image.properties.url})")
"""


async def main():
    # Generate a Python tool API
    # for the Brave Search MCP server
    await generate_mcp_sources(
        server_name="brave_search",
        server_params=SERVER_PARAMS,
        root_dir=Path("mcptools"),
    )

    # Launch ipybox code executor
    async with CodeExecutor() as executor:
        # Execute code that calls an MCP tool
        # programmatically in an IPython kernel
        async for item in executor.stream(CODE):
            match item:
                # Handle approval requests
                case ApprovalRequest() as req:
                    # Prompt user to approve or reject MCP tool call
                    prompt = f"Tool call: [{req}]\nApprove? (Y/n): "
                    if await arun(input, prompt) in ["y", ""]:
                        await req.accept()
                    else:
                        await req.reject()
                # Handle final execution result
                case CodeExecutionResult(text=text):
                    print(text)


if __name__ == "__main__":
    asyncio.run(main())
