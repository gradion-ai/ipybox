# Architecture

This page documents ipybox internal architecture for agent consumption.
The published architecture overview is in `docs/architecture.md`.

## Key Modules

- `ipybox/code_exec.py`: `CodeExecutor` - main API, orchestrates kernel and tool execution
- `ipybox/kernel_mgr/server.py`: `KernelGateway` - manages Jupyter Kernel Gateway subprocess
- `ipybox/kernel_mgr/client.py`: `KernelClient` - WebSocket client for kernel communication
- `ipybox/kernel_mgr/init.py`: `build_init_code()` - generates kernel initialization code
- `ipybox/mcp_server.py`: `MCPServer` - MCP server exposing ipybox capabilities

## CodeExecutor Parameters

- `approve_tool_calls` (default `True`): requires approval for MCP tool calls via `stream()`
- `approve_shell_cmds` (default `False`): requires approval for `!cmd` shell commands
- `require_shell_escape` (default `False`): blocks direct `subprocess`/`os.system()` to prevent bypassing shell command approval; requires `approve_shell_cmds=True`

## mcpygen Dependency

The following modules have been extracted to the [mcpygen](https://github.com/gradion-ai/mcpygen) package:

- `mcpygen.tool_exec.server`: `ToolServer` - FastAPI server managing MCP servers and tool calls
- `mcpygen.tool_exec.client`: `ToolRunner` - client for executing MCP tools on ToolServer
- `mcpygen.tool_exec.approval.server`: `ApprovalChannel` - server-side approval request workflow
- `mcpygen.tool_exec.approval.client`: `ApprovalClient` - client-side approval handling
- `mcpygen.apigen`: `generate_mcp_sources()` - generates typed Python wrappers from MCP schemas
- `mcpygen.client`: `MCPClient` - generic MCP client (stdio, SSE, streamable HTTP)

## Execution Flow

### MCP tool calls

1. User code calls a generated MCP wrapper function
2. Wrapper -> `ToolRunner.run_sync()` -> HTTP POST to ToolServer `/run`
3. ToolServer -> `ApprovalChannel.request()` -> WebSocket -> `ApprovalClient`
4. Application callback receives `ApprovalRequest`, calls `accept()`/`reject()`
5. If accepted: ToolServer executes the MCP tool on the MCP server
6. Result returned by generated wrapper function

### Shell commands

1. `!cmd` in IPython triggers custom handler installed by `build_init_code()`
2. Handler -> `ApprovalRequestor` -> ToolServer -> `ApprovalClient`
3. Application receives `ApprovalRequest(tool_name="shell", tool_args={"cmd": "..."})`
4. If accepted: handler executes original shell command
5. `require_shell_escape=True`: `ContextVar` guard blocks direct `subprocess.Popen`/`os.system()`, temporarily lifted during handler execution

## Kernel Initialization

`build_init_code()` composes optional init sections: env setup, cwd restore hook, shell approval handlers, subprocess guards. All internals use `_ipybox_` prefix, cleaned up after init. `KernelClient._rewrite_traceback()` hides these from error output.

## Code Generation

`generate_mcp_sources()` connects to an MCP server, discovers tools, and generates:
- One module per tool with `Params` (Pydantic), optional `Result`, and `run()` function
- `__init__.py` with ToolRunner setup
- Uses `datamodel-code-generator` for schema -> Pydantic conversion
