import socket
import subprocess
import tempfile
from pathlib import Path
from typing import Any, AsyncIterator, Iterator

import pytest
from sse_starlette.sse import AppStatus

from ipybox import DEFAULT_TAG, ExecutionClient, ExecutionContainer, ResourceClient
from tests.mcp_server import STDIO_SERVER_PATH, sse_server, streamable_http_server


@pytest.fixture(scope="package")
def ip_address() -> str:
    """Get the primary non-loopback IP address."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(0.1)
    s.connect(("8.8.8.8", 80))
    return s.getsockname()[0]


@pytest.fixture(scope="package")
def workspace():
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture(scope="package")
def container_image_root() -> Iterator[str]:
    yield build_container_image("test-root", root=True)


@pytest.fixture(scope="package")
def container_image_user() -> Iterator[str]:
    yield build_container_image("test", root=False)


@pytest.fixture(
    scope="package",
    params=["test-root", "test"],
)
def container_image(request, container_image_root, container_image_user) -> Iterator[str]:
    if request.param == "test-root":
        yield container_image_root
    else:
        yield container_image_user


@pytest.fixture(scope="package")
async def container(container_image: str, workspace: str) -> AsyncIterator[ExecutionContainer]:
    async with ExecutionContainer(
        tag=container_image,
        binds={workspace: "workspace"},
        env={"TEST_VAR": "test_val"},
    ) as container:
        yield container


@pytest.fixture
async def execution_client(container: ExecutionContainer) -> AsyncIterator[ExecutionClient]:
    async with ExecutionClient(host="localhost", port=container.executor_port) as client:
        yield client


@pytest.fixture
async def resource_client(container: ExecutionContainer) -> AsyncIterator[ResourceClient]:
    async with ResourceClient(host="localhost", port=container.resource_port) as client:
        yield client


@pytest.fixture(params=["stdio", "http", "sse"])
async def server_params(request, ip_address, reset_app_status) -> AsyncIterator[dict[str, Any]]:
    if request.param == "stdio":
        yield {
            "command": "python",
            "args": [str(STDIO_SERVER_PATH)],
        }
    elif request.param == "http":
        async with streamable_http_server() as server:
            yield {
                "type": "streamable_http",
                "url": f"http://{ip_address}:{server.settings.port}/mcp",
            }
    elif request.param == "sse":
        async with sse_server() as server:
            yield {
                "type": "sse",
                "url": f"http://{ip_address}:{server.settings.port}/sse",
            }


@pytest.fixture
def reset_app_status():
    yield
    AppStatus.should_exit_event = None


def build_container_image(suffix: str, root: bool = False) -> str:
    """Helper function to build container images."""
    tag = f"{DEFAULT_TAG}-{suffix}"
    deps_path = Path(__file__).parent / "dependencies.txt"

    cmd = ["python", "-m", "ipybox", "build", "-t", tag, "-d", str(deps_path)]
    if root:
        cmd.append("-r")

    subprocess.run(cmd, check=True)
    return tag
