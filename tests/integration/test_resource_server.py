import asyncio
import shutil
import tempfile
from pathlib import Path

import aiohttp
import pytest
import uvicorn

from ipybox import ResourceClient
from ipybox.resource.server import ResourceServer
from tests.mcp_server import MCP_SERVER_PATH


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)


@pytest.fixture
async def resource_server(temp_dir):
    """Start a ResourceServer in a separate task and clean up after tests."""
    server = ResourceServer(root_dir=temp_dir, host="127.0.0.1", port=9017)

    uvicorn_config = uvicorn.Config(server.app, host=server.host, port=server.port)
    uvicorn_server = uvicorn.Server(uvicorn_config)
    uvicorn_task = asyncio.create_task(uvicorn_server.serve())

    yield server

    uvicorn_server.should_exit = True
    await uvicorn_task


@pytest.fixture
async def resource_client(resource_server: ResourceServer):
    """Create a ResourceClient that connects to our test server."""
    async with ResourceClient(host="127.0.0.1", port=resource_server.port) as client:
        yield client


@pytest.mark.asyncio
async def test_get_modules_valid(resource_client):
    """Test getting sources for valid modules."""
    result = await resource_client.get_module_sources(["os", "json"])

    assert "os" in result
    assert "json" in result
    assert "import" in result["os"]  # Simple check that we got actual source code
    assert "import" in result["json"]


@pytest.mark.asyncio
async def test_get_modules_invalid(resource_client):
    """Test getting sources for an invalid module."""
    with pytest.raises(aiohttp.ClientResponseError) as excinfo:
        await resource_client.get_module_sources(["non_existent_module_123456789"])

    assert excinfo.value.status == 404


@pytest.mark.asyncio
async def test_get_modules_mixed_validity(resource_client):
    """Test getting sources for a mix of valid and invalid modules."""
    with pytest.raises(aiohttp.ClientResponseError) as excinfo:
        await resource_client.get_module_sources(["os", "non_existent_module_123456789"])

    assert excinfo.value.status == 404


@pytest.mark.asyncio
async def test_generate_mcp_with_real_server(resource_client, temp_dir):
    """Test generating MCP sources using tests/mcp_server.py."""
    # Copy MCP server to test directory in temporary root
    test_mcp_dir = temp_dir / "test_mcp_servers"
    test_mcp_dir.mkdir(exist_ok=True)
    shutil.copy(MCP_SERVER_PATH, test_mcp_dir / "mcp_server.py")

    server_params = {
        "command": "python",
        "args": [str(test_mcp_dir / "mcp_server.py")],
    }

    # Generate MCP client sources
    gen_result = await resource_client.generate_mcp_sources(
        relpath="generated_mcp", server_name="myTestServer", server_params=server_params
    )

    assert gen_result == ["tool_1", "tool_2"]

    # Verify files were created (indirectly through get_mcp_sources)
    sources = await resource_client.get_mcp_sources(relpath="generated_mcp", server_name="myTestServer")
    assert "tool_1" in sources
    assert "tool_2" in sources

    # Check content of sources
    assert "def tool_1(params: Params)" in sources["tool_1"]
    assert "def tool_2(params: Params)" in sources["tool_2"]

    # Also verify the files were physically created
    generated_dir = temp_dir / "generated_mcp" / "myTestServer"
    assert (generated_dir / "tool_1.py").exists()
    assert (generated_dir / "tool_2.py").exists()


@pytest.mark.asyncio
async def test_get_mcp_sources_nonexistent_server(resource_client):
    """Test getting MCP sources for a non-existent server."""
    with pytest.raises(aiohttp.ClientResponseError) as excinfo:
        await resource_client.get_mcp_sources(relpath="generated_mcp", server_name="non_existent_server")

    assert excinfo.value.status == 404


@pytest.mark.asyncio
async def test_get_mcp_sources_empty_server(resource_client, temp_dir):
    """Test getting MCP sources for a server with no relevant files."""
    # Create an empty server directory without Python files
    empty_server_dir = temp_dir / "generated_mcp" / "empty_server"
    empty_server_dir.mkdir(parents=True, exist_ok=True)

    # Add only __init__.py
    with open(empty_server_dir / "__init__.py", "w") as f:
        f.write("# Empty init file")

    # Get sources - should be an empty dictionary
    sources = await resource_client.get_mcp_sources(relpath="generated_mcp", server_name="empty_server")
    assert sources == {}
