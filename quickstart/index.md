# Quickstart

This guide walks through a complete example: generating a Python tool API for the [Brave Search MCP server](https://github.com/brave/brave-search-mcp-server), executing code that calls it, and handling tool call approvals.

## Installation

```
pip install ipybox
```

## Get a Brave API key

Sign up for a free API key at [api.search.brave.com](https://api.search.brave.com). Once you have your key, set it as an environment variable:

```
export BRAVE_API_KEY=your_api_key_here
```

Or create a `.env` file in your project root (ipybox loads it automatically):

```
BRAVE_API_KEY=your_api_key_here
```

## Complete example

```
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
```

## How it works

### Server parameters

The `server_params` dict defines how to connect to an MCP server. For stdio servers (local processes), you specify:

- `command`: The executable to run
- `args`: Command-line arguments
- `env`: Environment variables to pass

```
SERVER_PARAMS = {
    "command": "npx",
    "args": ["-y", "@brave/brave-search-mcp-server", "--transport", "stdio"],
    "env": {"BRAVE_API_KEY": "${BRAVE_API_KEY}"},
}
```

The `${BRAVE_API_KEY}` placeholder is replaced with the actual value from your environment when ipybox starts the MCP server.

### Generating a Python tool API

generate_mcp_sources() connects to the MCP server, discovers its tools, and generates a typed Python API from their schema:

```
await generate_mcp_sources(
    server_name="brave_search",
    server_params=SERVER_PARAMS,
    root_dir=Path("mcptools"),
)
```

This creates an `mcptools/brave_search` package with a Python module for each MCP server tool:

```
mcptools/brave_search/
├── __init__.py
├── brave_web_search.py
├── brave_local_search.py
├── brave_image_search.py
└── ...
```

Each module contains a Pydantic `Params` class for input validation, a `Result` class or `str` return type, and a `run()` function that executes the MCP tool.

### Code execution

CodeExecutor runs Python code in an IPython kernel. Variables and definitions persist across executions, enabling stateful workflows.

```
async with CodeExecutor() as executor:
    async for item in executor.stream(CODE):
        ...
```

The `stream()` method yields events as execution progresses. You'll receive ApprovalRequest events when the code calls an MCP tool, and a final CodeExecutionResult with the output.

### Tool call approval

When an MCP tool is called during code execution, ipybox pauses execution and sends an ApprovalRequest to your application. You must explicitly approve or reject each tool call:

```
case ApprovalRequest() as req:
    if user_approves:
        await req.accept()
    else:
        await req.reject()
```

The ApprovalRequest includes the server name, tool name, and arguments, so you can make informed decisions or implement custom approval logic.

## Next steps

- [API Generation](https://gradion-ai.github.io/ipybox/apigen/index.md) - Generating typed Python APIs from MCP tools
- [Code Execution](https://gradion-ai.github.io/ipybox/codeexec/index.md) - Running code and handling tool approvals
- [Sandboxing](https://gradion-ai.github.io/ipybox/sandbox/index.md) - Secure execution with network and filesystem isolation
