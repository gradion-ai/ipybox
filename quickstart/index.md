# Quickstart

This guide walks through Python code execution, shell commands, programmatic MCP tool calling, and application-level approval with ipybox.

## Installation

```
pip install ipybox
```

## Basic execution

CodeExecutor runs Python code and shell commands in an IPython kernel:

```
async with CodeExecutor() as executor:
    # Execute Python code
    result = await executor.execute("print('hello from Python')")
    print(result.text)

    # Execute a shell command
    result = await executor.execute("!echo hello from shell")
    print(result.text)

    # Mix Python and shell in one block
    code = """
    name = "ipybox"
    !echo hello from {name}

    # Capture shell output into a Python variable
    files = !ls /tmp
    print(f"found {len(files)} entries in /tmp")
    """
    result = await executor.execute(code)
    print(result.text)
```

Shell commands use IPython's `!` syntax and mix freely with Python code. `result = !cmd` captures shell output into a Python variable. Python variables are interpolated into shell commands via `{variable}` syntax. For multi-line shell scripts, use `%%bash` or `%%sh` cell magics.

## Programmatic MCP tool calling

ipybox can generate typed Python APIs from MCP server tool schemas via [mcpygen](https://gradion-ai.github.io/mcpygen/). The generated APIs can be imported and called like regular Python functions.

This example uses the [Brave Search MCP server](https://github.com/brave/brave-search-mcp-server). Sign up for a free API key at [api.search.brave.com](https://api.search.brave.com) and set it as an environment variable:

```
export BRAVE_API_KEY=your_api_key_here
```

`generate_mcp_sources()` connects to the MCP server, discovers its tools, and generates a typed Python package:

```
await generate_mcp_sources(
    server_name="brave_search",
    server_params=SERVER_PARAMS,
    root_dir=Path("mcptools"),
)
```

See [API Generation](https://gradion-ai.github.io/ipybox/apigen/index.md) for details on server parameters, generated package structure, and supported transports.

The generated API can then be imported and called in code submitted to `execute()`, which auto-approves all tool calls:

```
CODE = """
from mcptools.brave_search.brave_image_search import Params, Result, run

result: Result = run(Params(query="neural topic models", count=3))

for image in result.items:
    print(f"- [{image.title}]({image.properties.url})")
"""
```

```
async with CodeExecutor() as executor:
    result = await executor.execute(CODE)
    print(result.text)
```

## Streaming vs execute

`execute()` runs code to completion and auto-approves any tool calls and shell commands. For incremental output and control over [approvals](#approval), use `stream()` instead. `stream()` yields events as execution progresses:

- `ApprovalRequest` when code triggers a programmatic MCP tool call or a shell command
- CodeExecutionChunk for incremental output (when `chunks=True`)
- CodeExecutionResult with the final output

## Approval

Both MCP tool calls and shell commands can require application-level approval before execution. `approve_tool_calls` (default `True`) requires approval for MCP tool calls. `approve_shell_cmds` (default `False`) requires approval for `!cmd` shell commands and `%%bash`/`%%sh` cell magics.

The following example executes a code block that calls an MCP tool and runs a shell command, both requiring approval:

```
SEARCH_AND_ECHO = """
from mcptools.brave_search.brave_image_search import Params, Result, run

result: Result = run(Params(query="neural topic models", count=3))
!echo "Found {len(result.items)} images"
"""
```

```
async with CodeExecutor(
    approve_tool_calls=True,  # default
    approve_shell_cmds=True,
) as executor:
    async for item in executor.stream(SEARCH_AND_ECHO):
        match item:
            case ApprovalRequest(tool_name="shell" | "shell_magic", tool_args=args):
                print(f"Shell: {args['cmd']}")
                await item.accept()
            case ApprovalRequest(tool_name=name, tool_args=args):
                print(f"Tool call: {name}({args})")
                await item.accept()
            case CodeExecutionResult(text=text):
                print(text)
```

Both approval types yield an `ApprovalRequest`. The `tool_name` field distinguishes them: `"shell"` for `!` commands, `"shell_magic"` for `%%bash`/`%%sh` cell magics, and the MCP tool name for tool calls. Call `accept()` to continue or `reject()` to block execution.

## Next steps

- [Code Execution](https://gradion-ai.github.io/ipybox/codeexec/index.md) - Shell commands, mixing, approval, and streaming
- [API Generation](https://gradion-ai.github.io/ipybox/apigen/index.md) - Generating typed Python APIs from MCP tools
- [Sandboxing](https://gradion-ai.github.io/ipybox/sandbox/index.md) - Kernel isolation with filesystem and network restrictions
