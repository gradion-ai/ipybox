# Testing

## Framework

- pytest + pytest-asyncio
- Async tests use `@pytest.mark.asyncio` decorator
- Async fixtures use `@pytest_asyncio.fixture`

## Test organization

- Unit tests (`tests/unit/`): no external dependencies, no real servers
- Integration tests (`tests/integration/`): real Jupyter kernels, MCP servers, network

## Test MCP server (`tests/integration/mcp_server.py`)

- `STDIO_SERVER_PATH`: path to the test MCP server script (used as stdio transport)
- `create_server()`: creates a `FastMCP` instance with test tools (`tool-1`, `tool_2`, `tool_3`)
- `streamable_http_server()`: async context manager starting HTTP transport on port 8710
- `sse_server()`: async context manager starting SSE transport on port 8711
- `tool_3` returns structured `OuterResult` (nested Pydantic model) for testing structured output
