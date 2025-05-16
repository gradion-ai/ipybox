import subprocess
import tempfile
from pathlib import Path
from typing import Generator

import pytest

from ipybox import DEFAULT_TAG, ExecutionClient, ExecutionContainer, ResourceClient


@pytest.fixture(scope="package")
async def workspace():
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture(
    scope="package",
    params=["test-root", "test"],
)
def container_image(request) -> Generator[str, None, None]:
    tag_suffix = request.param
    tag = f"{DEFAULT_TAG}-{tag_suffix}"
    deps_path = Path(__file__).parent / "dependencies.txt"

    cmd = ["python", "-m", "ipybox", "build", "-t", tag, "-d", str(deps_path)]

    if tag_suffix == "test-root":
        cmd.append("-r")

    # Build the image using the CLI
    subprocess.run(cmd, check=True)

    yield tag


@pytest.fixture(scope="package")
async def container(container_image: str, workspace: str):
    async with ExecutionContainer(
        tag=container_image,
        binds={workspace: "workspace"},
        env={"TEST_VAR": "test_val"},
    ) as container:
        yield container


@pytest.fixture
async def execution_client(container: ExecutionContainer):
    async with ExecutionClient(host="localhost", port=container.executor_port) as client:
        yield client


@pytest.fixture
async def resource_client(container: ExecutionContainer):
    async with ResourceClient(host="localhost", port=container.resource_port) as client:
        yield client
