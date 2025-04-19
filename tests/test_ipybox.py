import asyncio
import shutil
import subprocess
from pathlib import Path
from typing import Generator

import aiofiles
import pytest
from PIL import Image

from ipybox import DEFAULT_TAG, ExecutionClient, ExecutionContainer, ExecutionError, ResourceClient


@pytest.fixture(
    scope="module",
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


@pytest.fixture(scope="module")
async def container(container_image: str, workspace: str):
    async with ExecutionContainer(
        tag=container_image,
        binds={workspace: "workspace"},
        env={"TEST_VAR": "test_val"},
    ) as container:
        yield container


@pytest.fixture(scope="module")
async def execution_client(container: ExecutionContainer):
    async with ExecutionClient(host="localhost", port=container.executor_port) as client:
        yield client


@pytest.fixture(scope="module")
async def resource_client(container: ExecutionContainer):
    async with ResourceClient(host="localhost", port=container.resource_port) as client:
        yield client


@pytest.mark.asyncio(loop_scope="module")
async def test_single_command_output(execution_client):
    result = await execution_client.execute("print('Hello, world!')")
    assert result.text == "Hello, world!"


@pytest.mark.asyncio(loop_scope="module")
async def test_multi_command_output(execution_client):
    code = """
print('first')
print('second')
print('third')
"""
    result = await execution_client.execute(code)
    assert result.text == "first\nsecond\nthird"


@pytest.mark.asyncio(loop_scope="module")
async def test_no_output(execution_client):
    result = await execution_client.execute("x = 1")
    assert result.text is None


@pytest.mark.asyncio(loop_scope="module")
async def test_long_output(execution_client):
    result = await execution_client.execute("print('a' * 500000)")
    assert result.text == "a" * 500000


@pytest.mark.asyncio(loop_scope="module")
async def test_long_output_multiline(execution_client):
    result = await execution_client.execute("""s = "a\\n" * 500000; print(s)""")
    assert result.text == ("a\n" * 500000).strip()


@pytest.mark.asyncio(loop_scope="module")
async def test_long_output_chunked(execution_client):
    code = """
import asyncio

for i in range(100):
    print("a")
    await asyncio.sleep(0.01)
"""
    result = await execution_client.execute(code)
    assert result.text == ("a\n" * 100).strip()


@pytest.mark.asyncio(loop_scope="module")
async def test_image_output(execution_client):
    code = """
from PIL import Image
import numpy as np

# Create a simple test image
img = Image.fromarray(np.zeros((100, 100, 3), dtype=np.uint8))
img.show()
"""
    result = await execution_client.execute(code)
    assert len(result.images) == 1
    assert isinstance(result.images[0], Image.Image)
    assert result.images[0].size == (100, 100)


@pytest.mark.asyncio(loop_scope="module")
async def test_multiple_image_output(execution_client):
    code = """
from PIL import Image
import numpy as np

# Create two test images
img1 = Image.fromarray(np.zeros((50, 50, 3), dtype=np.uint8))
img2 = Image.fromarray(np.ones((30, 30, 3), dtype=np.uint8) * 255)
img1.show()
img2.show()
"""
    result = await execution_client.execute(code)
    assert len(result.images) == 2
    assert isinstance(result.images[0], Image.Image)
    assert isinstance(result.images[1], Image.Image)
    assert result.images[0].size == (50, 50)
    assert result.images[1].size == (30, 30)


@pytest.mark.asyncio(loop_scope="module")
async def test_long_input(execution_client):
    code = "result = 0\n"
    code += "\n".join(f"result += {i}" for i in range(10000))
    code += "\nprint(result)"
    result = await execution_client.execute(code)
    assert result.text == str(sum(range(10000)))


@pytest.mark.asyncio(loop_scope="module")
async def test_runtime_error(execution_client):
    with pytest.raises(ExecutionError) as exc_info:
        await execution_client.execute("2 / 0")
    assert "ZeroDivisionError" in exc_info.value.args[0]
    assert "ZeroDivisionError" in exc_info.value.trace


@pytest.mark.asyncio(loop_scope="module")
async def test_syntax_error(execution_client):
    code = "while True print('Hello')"
    with pytest.raises(ExecutionError) as exc_info:
        await execution_client.execute(code)
    assert "SyntaxError" in exc_info.value.args[0]
    assert "SyntaxError" in exc_info.value.trace


@pytest.mark.asyncio(loop_scope="module")
async def test_interrupt_kernel(execution_client):
    code = """
a = 0
while True:
    a = 5
"""
    with pytest.raises(asyncio.TimeoutError):
        await execution_client.execute(code, timeout=1)
    result = await execution_client.execute("print(a)")
    assert result.text == "5"


@pytest.mark.asyncio(loop_scope="module")
async def test_env(execution_client: ExecutionClient):
    result = await execution_client.execute("import os; print(os.environ['TEST_VAR'])")
    assert result.text == "test_val"


@pytest.mark.asyncio(loop_scope="module")
async def test_binds(execution_client: ExecutionClient, workspace: str):
    async with aiofiles.open(Path(workspace) / "test_file", "w") as f:
        await f.write("test_content")

    result = await execution_client.execute("import os; print(open('workspace/test_file').read())")
    assert result.text == "test_content"


@pytest.mark.asyncio(loop_scope="module")
async def test_get_module_source(resource_client: ResourceClient):
    # Get the source through the resource server
    result = await resource_client.get_module_sources(["ipybox.modinfo"])
    source = result["ipybox.modinfo"]

    # Load the actual source file
    modinfo_path = Path("ipybox", "modinfo.py")
    with open(modinfo_path) as f:
        actual_source = f.read()

    assert source == actual_source


@pytest.mark.asyncio(loop_scope="module")
async def test_mcp(resource_client: ResourceClient, execution_client: ExecutionClient, workspace: str):
    # Copy MCP server to /app/workspace/mcp_server.py into the container
    mcp_server_path = Path(__file__).parent / "mcp_server.py"
    shutil.copy(mcp_server_path, Path(workspace) / "mcp_server.py")

    server_params = {
        "command": "python",
        "args": ["workspace/mcp_server.py"],
    }

    # generate MCP client sources in /app/mcpgen/test
    gen_result = await resource_client.generate_mcp_sources(
        relpath="mcpgen", server_name="test", server_params=server_params
    )
    assert gen_result == ["get_weather"]

    # retrieve the generated sources via ipybox filesystem
    get_result_1 = await resource_client.get_mcp_sources(relpath="mcpgen", server_name="test")
    source_1 = get_result_1["get_weather"]

    module_name = "mcpgen.test.get_weather"

    # get the generated sources via ipybox module loading
    get_result_2 = await resource_client.get_module_sources([module_name])

    # check if retrieval mechanisms are equivalent
    assert get_result_1["get_weather"] == get_result_2[module_name]

    # check if it contains the generated function signature
    assert "get_weather(params: Params)" in source_1

    # Execute the MCP server via the generated function
    exec_result = await execution_client.execute("""
from mcpgen.test.get_weather import get_weather, Params
print(get_weather(Params(city="Graz")))
""")
    assert exec_result.text == "The weather in Graz is sunny"
