from typing import Any, AsyncIterator

import pytest
from sse_starlette.sse import AppStatus

from ipybox.mcp.run import run_async
from tests.mcp_server import STDIO_SERVER_PATH, sse_server, streamable_http_server


@pytest.fixture
def reset_app_status():
    yield
    AppStatus.should_exit_event = None


@pytest.fixture(params=["stdio", "http", "sse"])
async def server_params(request, reset_app_status) -> AsyncIterator[dict[str, Any]]:
    if request.param == "stdio":
        yield {
            "command": "python",
            "args": [str(STDIO_SERVER_PATH)],
        }
    elif request.param == "http":
        async with streamable_http_server() as server:
            yield {
                "type": "streamable_http",
                "url": f"http://localhost:{server.settings.port}/mcp",
            }
    elif request.param == "sse":
        async with sse_server() as server:
            yield {
                "type": "sse",
                "url": f"http://localhost:{server.settings.port}/sse",
            }


async def test_server(server_params: dict[str, Any]):
    result = await run_async("tool-1", {"s": "test"}, server_params)
    assert result == "You passed to tool 1: test"
