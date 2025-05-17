import asyncio
import shutil
from pathlib import Path

import aiofiles
import pytest
from flaky import flaky
from PIL import Image

from ipybox import ExecutionClient, ExecutionError, ResourceClient
from tests.mcp_server import MCP_SERVER_PATH


@pytest.mark.asyncio
async def test_single_command_output(execution_client: ExecutionClient):
    result = await execution_client.execute("print('Hello, world!')")
    assert result.text == "Hello, world!"


@pytest.mark.asyncio
async def test_multi_command_output(execution_client: ExecutionClient):
    code = """
print('first')
print('second')
print('third')
"""
    result = await execution_client.execute(code)
    assert result.text == "first\nsecond\nthird"


@pytest.mark.asyncio
async def test_stateful_execution(execution_client: ExecutionClient):
    await execution_client.execute("x = 1")
    await execution_client.execute("y = x + 1")
    result = await execution_client.execute('print(f"{x},{y}")')
    assert result.text == "1,2"


@pytest.mark.asyncio
async def test_no_output(execution_client: ExecutionClient):
    result = await execution_client.execute("x = 1")
    assert result.text is None


@pytest.mark.asyncio
async def test_long_output(execution_client: ExecutionClient):
    result = await execution_client.execute("print('a' * 500000)")
    assert result.text == "a" * 500000


@pytest.mark.asyncio
async def test_long_output_multiline(execution_client: ExecutionClient):
    result = await execution_client.execute("""s = "a\\n" * 500000; print(s)""")
    assert result.text == ("a\n" * 500000).strip()


@pytest.mark.asyncio
async def test_long_output_chunked(execution_client: ExecutionClient):
    code = """
import asyncio

for i in range(100):
    print("a")
    await asyncio.sleep(0.01)
"""
    result = await execution_client.execute(code)
    assert result.text == ("a\n" * 100).strip()


@pytest.mark.asyncio
async def test_image_output(execution_client: ExecutionClient):
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


@pytest.mark.asyncio
@flaky(max_runs=3, min_passes=1)
async def test_multiple_image_output(execution_client: ExecutionClient):
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


@pytest.mark.asyncio
async def test_long_input(execution_client: ExecutionClient):
    code = "result = 0\n"
    code += "\n".join(f"result += {i}" for i in range(10000))
    code += "\nprint(result)"
    result = await execution_client.execute(code)
    assert result.text == str(sum(range(10000)))


@pytest.mark.asyncio
async def test_runtime_error(execution_client: ExecutionClient):
    with pytest.raises(ExecutionError) as exc_info:
        await execution_client.execute("2 / 0")
    assert "ZeroDivisionError" in exc_info.value.args[0]
    assert "ZeroDivisionError" in exc_info.value.trace


@pytest.mark.asyncio
async def test_syntax_error(execution_client: ExecutionClient):
    code = "while True print('Hello')"
    with pytest.raises(ExecutionError) as exc_info:
        await execution_client.execute(code)
    assert "SyntaxError" in exc_info.value.args[0]
    assert "SyntaxError" in exc_info.value.trace


@pytest.mark.asyncio
async def test_interrupt_kernel(execution_client: ExecutionClient):
    code = """
a = 0
while True:
    a = 5
"""
    with pytest.raises(asyncio.TimeoutError):
        await execution_client.execute(code, timeout=1)
    result = await execution_client.execute("print(a)")
    assert result.text == "5"


@pytest.mark.asyncio
async def test_env(execution_client: ExecutionClient):
    result = await execution_client.execute("import os; print(os.environ['TEST_VAR'])")
    assert result.text == "test_val"


@pytest.mark.asyncio
async def test_binds(execution_client: ExecutionClient, workspace: str):
    async with aiofiles.open(Path(workspace) / "test_file", "w") as f:
        await f.write("test_content")

    result = await execution_client.execute("import os; print(open('workspace/test_file').read())")
    assert result.text == "test_content"


@pytest.mark.asyncio
async def test_mcp_client_function(resource_client: ResourceClient, execution_client: ExecutionClient, workspace: str):
    # Copy MCP server to /app/workspace/mcp_server.py into the container
    shutil.copy(MCP_SERVER_PATH, Path(workspace) / "mcp_server.py")

    server_params = {
        "command": "python",
        "args": ["workspace/mcp_server.py"],
    }

    # generate MCP client sources in /app/mcpgen/test
    await resource_client.generate_mcp_sources(relpath="mcpgen", server_name="test", server_params=server_params)

    # Execute the MCP server via the generated function
    exec_result = await execution_client.execute("""
from mcpgen.test.tool_1 import tool_1, Params
print(tool_1(Params(s="Hello")))
""")
    assert exec_result.text == "You passed to tool 1: Hello"
