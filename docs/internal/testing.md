# Testing

## Framework

- pytest + pytest-asyncio
- Async tests use `@pytest.mark.asyncio` decorator
- Async fixtures use `@pytest_asyncio.fixture`

## Test organization

- Unit tests (`tests/unit/`): no external dependencies, no real servers
- Integration tests (`tests/integration/`): real IPython kernels, MCP servers, network

## Unit tests

- `test_code_exec_helpers.py`: execution budget, stream worker
- `test_kernel_gateway.py`: KernelGateway subprocess configuration
- `test_kernel_init.py`: `build_init_code()` output sections and variable cleanup
- `test_rewrite_traceback.py`: `_ipybox_` filtering, `get_ipython().system()` rewriting

## Integration tests

- `test_code_exec.py`: CodeExecutor end-to-end (execution, streaming, approval, rejection, timeouts)
- `test_kernel_init.py`: ANSI stripping, variable cleanup
- `test_kernel_mgr.py`: KernelClient and KernelGateway integration
- `test_shell_cmds.py`: shell command approval and subprocess blocking
- `test_mcp_server.py`: MCPServer functionality

## Test MCP server (`tests/integration/mcp_server.py`)

- `STDIO_SERVER_PATH`: path to the test MCP server script (used as stdio transport)
- `create_server()`: creates a `FastMCP` instance with test tools (`tool-1`, `tool_2`, `tool_3`)
- `streamable_http_server()`: async context manager starting HTTP transport on port 8710
- `sse_server()`: async context manager starting SSE transport on port 8711
- `tool_3` returns structured `OuterResult` (nested Pydantic model) for testing structured output
