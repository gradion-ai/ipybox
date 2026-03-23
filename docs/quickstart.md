# Quickstart

This guide walks through Python code execution, shell commands, programmatic MCP tool calling, and application-level approval with ipybox.

## Installation

```bash
pip install ipybox
```

## Basic execution

[`CodeExecutor`][ipybox.CodeExecutor] runs Python code and shell commands in an IPython kernel:

```python
--8<-- "examples/quickstart.py:basic_execution"
```

Shell commands use IPython's `!` syntax and mix freely with Python code. `result = !cmd` captures shell output into a Python variable. Python variables are interpolated into shell commands via `{variable}` syntax. For multi-line shell scripts, use `%%bash` or `%%sh` cell magics.

## Programmatic MCP tool calling

ipybox can generate typed Python APIs from MCP server tool schemas via [mcpygen](https://gradion-ai.github.io/mcpygen/). The generated APIs can be imported and called like regular Python functions.

This example uses the [Brave Search MCP server](https://github.com/brave/brave-search-mcp-server). Sign up for a free API key at [api.search.brave.com](https://api.search.brave.com) and set it as an environment variable:

```bash
export BRAVE_API_KEY=your_api_key_here
```

`generate_mcp_sources()` connects to the MCP server, discovers its tools, and generates a typed Python package:

```python
await generate_mcp_sources(
    server_name="brave_search",
    server_params=SERVER_PARAMS,
    root_dir=Path("mcptools"),
)
```

See [API Generation](apigen.md) for details on server parameters, generated package structure, and supported transports.

The generated API can then be imported and called in code submitted to `execute()`, which auto-approves all tool calls:

```python
--8<-- "examples/quickstart.py:tool_call_code"
```

```python
--8<-- "examples/quickstart.py:tool_call_execute"
```

## Streaming vs execute

`execute()` runs code to completion and auto-approves any tool calls and shell commands. For incremental output and control over [approvals](#approval), use `stream()` instead. `stream()` yields events as execution progresses:

- `ApprovalRequest` when code triggers a programmatic MCP tool call or a shell command
- [`CodeExecutionChunk`][ipybox.CodeExecutionChunk] for incremental output (when `chunks=True`)
- [`CodeExecutionResult`][ipybox.CodeExecutionResult] with the final output

## Approval

Both MCP tool calls and shell commands can require application-level approval before execution. `approve_tool_calls` (default `True`) requires approval for MCP tool calls. `approve_shell_cmds` (default `False`) requires approval for `!cmd` shell commands and `%%bash`/`%%sh` cell magics.

The following example executes a code block that calls an MCP tool and runs a shell command, both requiring approval:

```python
--8<-- "examples/quickstart.py:approval_code"
```

```python
--8<-- "examples/quickstart.py:approval"
```

Both approval types yield an `ApprovalRequest`. The `tool_name` field distinguishes them: `"shell"` for `!` commands, `"shell_magic"` for `%%bash`/`%%sh` cell magics, and the MCP tool name for tool calls. Call `accept()` to continue or `reject()` to block execution.

## Next steps

- [Code Execution](codeexec.md) - Shell commands, mixing, approval, and streaming
- [API Generation](apigen.md) - Generating typed Python APIs from MCP tools
- [Sandboxing](sandbox.md) - Kernel isolation with filesystem and network restrictions
