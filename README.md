# ipybox

ipybox is a Python code execution sandbox with first-class support for programmatic MCP tool use. It generates typed Python wrapper functions from MCP server tool schemas, supporting both local stdio and remote HTTP servers. Code that calls these generated functions executes in a sandboxed IPython kernel, providing a stateful environment where variables and definitions persist across executions. Generated wrapper functions delegate MCP tool execution to a separate environment that enforces tool call approval, requiring applications to explicitly accept or reject each tool call before it executes.

ipybox is designed for agents that interact with their environment through code actions rather than JSON tool calls, a more reliable approach since LLMs are pretrained extensively on Python code. Agents generate and execute Python code that composes multiple MCP tool calls into a single action, using loops, conditionals, and data transformations that keep intermediate results out of the agent's context window. Since agent-generated code cannot be trusted, it must run in a secure sandboxed environment, and all MCP tool calls must be approved by the application. ipybox supports both with minimal setup.

## Python SDK

ipybox provides a Python SDK for executing code that calls MCP tools. First, generate typed wrapper functions from an MCP server:

```python
from pathlib import Path
from ipybox import generate_mcp_sources

server_params = {
    "command": "npx",
    "args": ["-y", "@brave/brave-search-mcp-server", "--transport", "stdio"],
    "env": {"BRAVE_API_KEY": "{BRAVE_API_KEY}"},
}

await generate_mcp_sources("brave_search", server_params, Path("mcptools"))
```

This generates typed wrapper functions like `run` in [`mcptools/brave_search/brave_image_search.py`](mcptools/brave_search/brave_image_search.py). Then execute code that uses the generated wrappers:

```python
import asyncio
from ipybox import ApprovalRequest, CodeExecutionResult, CodeExecutor

CODE = """
from mcptools.brave_search import brave_image_search

result = brave_image_search.run(brave_image_search.Params(query="robo cats", count=5))

for image in result.items:
    print(f"- [{image.title}]({image.properties.url})")
"""

async def main():
    async with CodeExecutor() as executor:
        async for item in executor.execute(CODE):
            match item:
                case ApprovalRequest():
                    await item.accept()
                case CodeExecutionResult():
                    print(item.text)

asyncio.run(main())
```

## MCP Server

ipybox can also be used as an MCP server, exposing code execution to MCP clients like Claude Desktop. Add to your Claude Desktop config:

```json
{
  "mcpServers": {
    "ipybox": {
      "command": "python",
      "args": ["-m", "ipybox.mcp_server"]
    }
  }
}
```

The server provides tools for registering MCP servers, installing packages, and executing Python code in a stateful IPython kernel.
