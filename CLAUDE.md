# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

```bash
uv sync                      # Install/sync dependencies
uv run invoke precommit-install  # Set up pre-commit hooks (once, after initial sync)
uv add <dep>                 # Add dependency (--dev for dev deps)
uv run invoke cc             # Run code checks (auto-fixes formatting, mypy errors need manual fix)
uv run invoke test           # Run all tests
uv run invoke ut             # Run unit tests only
uv run invoke it             # Run integration tests only
uv run invoke test --cov     # Run tests with coverage

# Single test file
uv run pytest -xsv tests/integration/test_[name].py

# Single test
uv run pytest -xsv tests/integration/test_[name].py::test_name

# Documentation
uv run invoke build-docs     # Build docs
uv run invoke serve-docs     # Serve docs at localhost:8000
```

**Note:** `invoke cc` only checks files under version control. Run `git add` on new files first.

## Architecture

### Key Modules

- `ipybox/code_exec.py`: `CodeExecutor` - main API, orchestrates kernel and tool execution
- `ipybox/kernel_mgr/server.py`: `KernelGateway` - manages Jupyter Kernel Gateway subprocess
- `ipybox/kernel_mgr/client.py`: `KernelClient` - WebSocket client for kernel communication
- `ipybox/tool_exec/server.py`: `ToolServer` - FastAPI server managing MCP servers and tool calls
- `ipybox/tool_exec/client.py`: `ToolRunner` - client for executing MCP tools on ToolServer
- `ipybox/tool_exec/approval/`: `ApprovalChannel`/`ApprovalClient` - approval request workflow
- `ipybox/mcp_apigen.py`: `generate_mcp_sources()` - generates typed Python wrappers from MCP schemas
- `ipybox/mcp_server.py`: `IpyboxMCPServer` - MCP server exposing ipybox capabilities
- `ipybox/mcp_client.py`: `MCPClient` - generic MCP client (stdio, SSE, streamable HTTP)

### Execution Flow

1. User code calls a generated MCP wrapper function
2. Wrapper -> `ToolRunner.run_sync()` -> HTTP POST to ToolServer `/run`
3. ToolServer -> `ApprovalChannel.request()` -> WebSocket -> `ApprovalClient`
4. Application callback receives `ApprovalRequest`, calls `accept()`/`reject()`
5. If accepted: ToolServer executes the MCP tool on the MCP server
6. Result returned by generated wrapper function

### Code Generation

`generate_mcp_sources()` connects to an MCP server, discovers tools, and generates:
- One module per tool with `Params` (Pydantic), optional `Result`, and `run()` function
- `__init__.py` with ToolRunner setup
- Uses `datamodel-code-generator` for schema -> Pydantic conversion
