import asyncio
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import aiohttp
import pytest
import uvicorn

from ipybox import ResourceClient
from ipybox.resource.server import ResourceServer
from tests.mcp_server import STDIO_SERVER_PATH


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("sys.path", sys.path + [tmp_dir]):
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
    shutil.copy(STDIO_SERVER_PATH, test_mcp_dir / "mcp_server.py")

    server_params = {
        "command": "python",
        "args": [str(test_mcp_dir / "mcp_server.py")],
    }

    # Generate MCP client sources
    gen_result = await resource_client.generate_mcp_sources(
        relpath="generated_mcp", server_name="myTestServer", server_params=server_params
    )

    assert gen_result == ["tool_1", "tool_2", "tool_3"]

    # Verify files were created (indirectly through get_mcp_sources)
    generated_sources = await resource_client.get_mcp_sources(relpath="generated_mcp", server_name="myTestServer")
    generated_dir = temp_dir / "generated_mcp" / "myTestServer"

    for tool_name in ["tool_1", "tool_2", "tool_3"]:
        assert tool_name in generated_sources
        assert (generated_dir / f"{tool_name}.py").exists()
        assert f"def {tool_name}(params: Params)" in generated_sources[tool_name]


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


@pytest.mark.asyncio
async def test_get_mcp_descriptions_valid_server(resource_client, temp_dir):
    """Test getting MCP descriptions for a valid server with tools."""
    # Copy MCP server to test directory
    test_mcp_dir = temp_dir / "test_mcp_servers"
    test_mcp_dir.mkdir(exist_ok=True)
    shutil.copy(STDIO_SERVER_PATH, test_mcp_dir / "mcp_server.py")

    # Create parent directory with __init__.py for proper module import
    mcp_parent_dir = temp_dir / "generated_mcp"
    mcp_parent_dir.mkdir(exist_ok=True)
    (mcp_parent_dir / "__init__.py").write_text("")

    server_params = {
        "command": "python",
        "args": [str(test_mcp_dir / "mcp_server.py")],
    }

    # Generate MCP client sources
    await resource_client.generate_mcp_sources(
        relpath="generated_mcp", server_name="myTestServer", server_params=server_params
    )

    # Get descriptions for all tools
    descriptions = await resource_client.get_mcp_descriptions(relpath="generated_mcp", server_name="myTestServer")

    # Verify we got descriptions for all three tools
    assert "tool_1" in descriptions
    assert "tool_2" in descriptions
    assert "tool_3" in descriptions

    # Verify descriptions are strings (docstrings)
    assert isinstance(descriptions["tool_1"], str)
    assert isinstance(descriptions["tool_2"], str)
    assert isinstance(descriptions["tool_3"], str)

    # Verify descriptions contain expected content from mcp_server.py docstrings
    assert "This is tool 1" in descriptions["tool_1"]
    assert "This is tool 2" in descriptions["tool_2"]
    assert "This is tool 3 with nested structured output" in descriptions["tool_3"]


@pytest.mark.asyncio
async def test_get_mcp_descriptions_nonexistent_server(resource_client):
    """Test getting MCP descriptions for a non-existent server."""
    with pytest.raises(aiohttp.ClientResponseError) as excinfo:
        await resource_client.get_mcp_descriptions(relpath="generated_mcp", server_name="non_existent_server")

    assert excinfo.value.status == 404


@pytest.mark.asyncio
async def test_get_mcp_descriptions_empty_server(resource_client, temp_dir):
    """Test getting MCP descriptions for a server with only __init__.py."""
    # Create an empty server directory
    empty_server_dir = temp_dir / "generated_mcp" / "empty_server"
    empty_server_dir.mkdir(parents=True, exist_ok=True)

    # Add only __init__.py
    with open(empty_server_dir / "__init__.py", "w") as f:
        f.write("# Empty init file")

    # Get descriptions - should be an empty dictionary
    descriptions = await resource_client.get_mcp_descriptions(relpath="generated_mcp", server_name="empty_server")
    assert descriptions == {}


@pytest.mark.asyncio
async def test_get_mcp_server_names_multiple_servers(resource_client, temp_dir):
    """Test listing multiple MCP servers in a directory."""
    # Copy MCP server to test directory
    test_mcp_dir = temp_dir / "test_mcp_servers"
    test_mcp_dir.mkdir(exist_ok=True)
    shutil.copy(STDIO_SERVER_PATH, test_mcp_dir / "mcp_server.py")

    # Create parent directory with __init__.py for proper module import
    mcp_parent_dir = temp_dir / "generated_mcp"
    mcp_parent_dir.mkdir(exist_ok=True)
    (mcp_parent_dir / "__init__.py").write_text("")

    server_params = {
        "command": "python",
        "args": [str(test_mcp_dir / "mcp_server.py")],
    }

    # Generate multiple MCP servers
    await resource_client.generate_mcp_sources(
        relpath="generated_mcp", server_name="server1", server_params=server_params
    )
    await resource_client.generate_mcp_sources(
        relpath="generated_mcp", server_name="server2", server_params=server_params
    )
    await resource_client.generate_mcp_sources(
        relpath="generated_mcp", server_name="server3", server_params=server_params
    )

    # List all servers
    server_names = await resource_client.get_mcp_server_names(relpath="generated_mcp")

    # Verify all three servers are listed
    assert sorted(server_names) == ["server1", "server2", "server3"]


@pytest.mark.asyncio
async def test_get_mcp_server_names_empty_directory(resource_client, temp_dir):
    """Test listing MCP servers in an empty directory."""
    # Create an empty directory
    empty_dir = temp_dir / "empty_mcp"
    empty_dir.mkdir(exist_ok=True)

    # List servers - should be empty
    server_names = await resource_client.get_mcp_server_names(relpath="empty_mcp")
    assert server_names == []


@pytest.mark.asyncio
async def test_get_mcp_server_names_nonexistent_path(resource_client):
    """Test listing MCP servers for a non-existent path."""
    with pytest.raises(aiohttp.ClientResponseError) as excinfo:
        await resource_client.get_mcp_server_names(relpath="non_existent_path")

    assert excinfo.value.status == 404


@pytest.mark.asyncio
async def test_get_mcp_server_names_mixed_content(resource_client, temp_dir):
    """Test that only directories are returned, not files."""
    # Create a directory with mixed content
    mixed_dir = temp_dir / "mixed_mcp"
    mixed_dir.mkdir(exist_ok=True)

    # Create subdirectories (servers)
    (mixed_dir / "server1").mkdir()
    (mixed_dir / "server2").mkdir()

    # Create files (should be ignored)
    with open(mixed_dir / "file1.py", "w") as f:
        f.write("# File 1")
    with open(mixed_dir / "file2.txt", "w") as f:
        f.write("# File 2")

    # List servers - should only return directories
    server_names = await resource_client.get_mcp_server_names(relpath="mixed_mcp")
    assert sorted(server_names) == ["server1", "server2"]


@pytest.mark.asyncio
async def test_generate_list_and_describe_workflow(resource_client, temp_dir):
    """Test the complete workflow: generate → list → describe."""
    # Copy MCP server to test directory
    test_mcp_dir = temp_dir / "test_mcp_servers"
    test_mcp_dir.mkdir(exist_ok=True)
    shutil.copy(STDIO_SERVER_PATH, test_mcp_dir / "mcp_server.py")

    # Create parent directory with __init__.py for proper module import
    mcp_parent_dir = temp_dir / "workflow_test"
    mcp_parent_dir.mkdir(exist_ok=True)
    (mcp_parent_dir / "__init__.py").write_text("")

    server_params = {
        "command": "python",
        "args": [str(test_mcp_dir / "mcp_server.py")],
    }

    # Step 1: Generate two MCP servers
    tools1 = await resource_client.generate_mcp_sources(
        relpath="workflow_test", server_name="server_a", server_params=server_params
    )
    tools2 = await resource_client.generate_mcp_sources(
        relpath="workflow_test", server_name="server_b", server_params=server_params
    )

    assert tools1 == ["tool_1", "tool_2", "tool_3"]
    assert tools2 == ["tool_1", "tool_2", "tool_3"]

    # Step 2: List all servers
    server_names = await resource_client.get_mcp_server_names(relpath="workflow_test")
    assert sorted(server_names) == ["server_a", "server_b"]

    # Step 3: Get descriptions for each server
    descriptions_a = await resource_client.get_mcp_descriptions(relpath="workflow_test", server_name="server_a")
    descriptions_b = await resource_client.get_mcp_descriptions(relpath="workflow_test", server_name="server_b")

    # Verify descriptions contain all tools
    assert set(descriptions_a.keys()) == {"tool_1", "tool_2", "tool_3"}
    assert set(descriptions_b.keys()) == {"tool_1", "tool_2", "tool_3"}

    # Verify all descriptions are strings
    for desc in descriptions_a.values():
        assert isinstance(desc, str)
    for desc in descriptions_b.values():
        assert isinstance(desc, str)
