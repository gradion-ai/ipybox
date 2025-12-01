import socket
from typing import Any, AsyncIterator

import pytest
import pytest_asyncio

from tests.integration.mcp_server import STDIO_SERVER_PATH, sse_server, streamable_http_server


@pytest.fixture(scope="package")
def ip_address() -> str:
    """Get the primary non-loopback IP address."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(0.1)
    s.connect(("8.8.8.8", 80))
    return s.getsockname()[0]


@pytest_asyncio.fixture
async def stdio_server_params() -> AsyncIterator[dict[str, Any]]:
    yield {
        "command": "python",
        "args": [str(STDIO_SERVER_PATH)],
    }


@pytest_asyncio.fixture
async def http_server_params(ip_address) -> AsyncIterator[dict[str, Any]]:
    async with streamable_http_server() as server:
        yield {
            "type": "streamable_http",
            "url": f"http://{ip_address}:{server.settings.port}/mcp",
        }


@pytest_asyncio.fixture
async def sse_server_params(ip_address) -> AsyncIterator[dict[str, Any]]:
    async with sse_server() as server:
        yield {
            "type": "sse",
            "url": f"http://{ip_address}:{server.settings.port}/sse",
        }
