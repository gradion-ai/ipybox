# Architecture

This page documents ipybox internal architecture for agent consumption.
The published architecture overview is in `docs/architecture.md`.

## Key Modules

- `ipybox/code_exec.py`: `CodeExecutor` - main API, orchestrates kernel and tool execution
- `ipybox/kernel_mgr/server.py`: `KernelGateway` - manages Jupyter Kernel Gateway subprocess
- `ipybox/kernel_mgr/client.py`: `KernelClient` - WebSocket client for kernel communication
- `ipybox/mcp_server.py`: `IpyboxMCPServer` - MCP server exposing ipybox capabilities

## mcpygen Dependency

The following modules have been extracted to the [mcpygen](https://github.com/gradion-ai/mcpygen) package:

- `mcpygen.tool_exec.server`: `ToolServer` - FastAPI server managing MCP servers and tool calls
- `mcpygen.tool_exec.client`: `ToolRunner` - client for executing MCP tools on ToolServer
- `mcpygen.tool_exec.approval.server`: `ApprovalChannel` - server-side approval request workflow
- `mcpygen.tool_exec.approval.client`: `ApprovalClient` - client-side approval handling
- `mcpygen.apigen`: `generate_mcp_sources()` - generates typed Python wrappers from MCP schemas
- `mcpygen.client`: `MCPClient` - generic MCP client (stdio, SSE, streamable HTTP)

## Execution Flow

1. User code calls a generated MCP wrapper function
2. Wrapper -> `ToolRunner.run_sync()` -> HTTP POST to ToolServer `/run`
3. ToolServer -> `ApprovalChannel.request()` -> WebSocket -> `ApprovalClient`
4. Application callback receives `ApprovalRequest`, calls `accept()`/`reject()`
5. If accepted: ToolServer executes the MCP tool on the MCP server
6. Result returned by generated wrapper function

## Code Generation

`generate_mcp_sources()` connects to an MCP server, discovers tools, and generates:
- One module per tool with `Params` (Pydantic), optional `Result`, and `run()` function
- `__init__.py` with ToolRunner setup
- Uses `datamodel-code-generator` for schema -> Pydantic conversion
