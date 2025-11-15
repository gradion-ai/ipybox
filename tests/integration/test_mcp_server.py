"""Integration tests for the ipybox MCP server."""

import sys
import tempfile
from pathlib import Path
from typing import AsyncIterator

import pytest
import pytest_asyncio
from mcp import ClientSession
from PIL import Image

from ipybox.mcp.run import mcp_client


@pytest.fixture(scope="module")
def mcp_server_workspace():
    """Create a temporary workspace for MCP server tests."""
    with tempfile.TemporaryDirectory(prefix="ipybox_mcp_test_") as temp_dir:
        temp_path = Path(temp_dir)

        yield {
            "temp_dir": temp_path,
        }


@pytest.fixture(scope="module")
def mcp_server_params(mcp_server_workspace, container_image):
    """Server parameters for connecting to MCP server."""
    workspace = mcp_server_workspace

    return {
        "command": sys.executable,
        "args": [
            "-m",
            "ipybox",
            "mcp",
            "--container-tag",
            container_image,
            "--allowed-dir",
            str(workspace["temp_dir"]),
        ],
    }


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def session(mcp_server_params) -> AsyncIterator[ClientSession]:
    """Create an MCP client session for each test."""
    try:
        async with mcp_client(mcp_server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session
    except Exception:
        pass


@pytest.mark.asyncio(loop_scope="module")
async def test_reset(session: ClientSession):
    """Test resetting the IPython kernel."""
    # Set a variable
    await session.call_tool(
        "execute_ipython_cell",
        arguments={
            "code": "test_var = 'before_reset'",
        },
    )

    # Verify variable exists
    result = await session.call_tool(
        "execute_ipython_cell",
        arguments={
            "code": "print(test_var)",
        },
    )
    assert "before_reset" in result.content[0].text

    # Reset the kernel
    result = await session.call_tool("reset", arguments={})
    assert not result.isError
    assert not result.content

    # Verify variable no longer exists
    result = await session.call_tool(
        "execute_ipython_cell",
        arguments={
            "code": "try:\n    print(test_var)\nexcept NameError:\n    print('Variable not defined')",
        },
    )
    assert "Variable not defined" in result.content[0].text


@pytest.mark.asyncio(loop_scope="module")
async def test_execute_simple_code(session: ClientSession):
    """Test executing simple Python code."""
    # Execute code
    result = await session.call_tool(
        "execute_ipython_cell",
        arguments={
            "code": "print('Hello, World!')\nresult = 2 + 2\nprint(f'Result: {result}')",
        },
    )

    assert not result.isError
    output = result.content[0].text

    assert "Hello, World!" in output
    assert "Result: 4" in output


@pytest.mark.asyncio(loop_scope="module")
async def test_execute_stateful(session: ClientSession):
    """Test that execution is stateful."""
    # First execution: define variable
    await session.call_tool(
        "execute_ipython_cell",
        arguments={
            "code": "x = 42",
        },
    )

    # Second execution: use variable
    result = await session.call_tool(
        "execute_ipython_cell",
        arguments={
            "code": "print(f'x = {x}')",
        },
    )

    assert "x = 42" in result.content[0].text


@pytest.mark.asyncio(loop_scope="module")
async def test_execute_with_error(session: ClientSession):
    """Test code execution with errors."""
    # Execute code with error
    result = await session.call_tool(
        "execute_ipython_cell",
        arguments={
            "code": "print('Before error')\n1/0\nprint('After error')",
        },
    )

    assert result.isError
    content = result.content[0].text

    assert "Before error" in content
    assert "ZeroDivisionError" in content


@pytest.mark.asyncio(loop_scope="module")
async def test_execute_with_image(session: ClientSession, mcp_server_workspace):
    """Test code execution that generates images."""
    workspace = mcp_server_workspace

    # First install matplotlib
    await session.call_tool(
        "execute_ipython_cell",
        arguments={
            "code": "!pip install matplotlib",
        },
    )

    # Generate and save a figure
    code = """
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend

# Create a simple plot
fig, ax = plt.subplots(figsize=(6, 4))
ax.plot([1, 2, 3, 4], [1, 4, 2, 3], 'b-')
ax.set_title('Test Plot')
ax.set_xlabel('X axis')
ax.set_ylabel('Y axis')

# Save the figure to a file in the container
fig.savefig('/app/test_plot.png', dpi=100, bbox_inches='tight')
print('Figure saved to /app/test_plot.png')
plt.close(fig)
"""

    result = await session.call_tool(
        "execute_ipython_cell",
        arguments={
            "code": code,
        },
    )

    assert not result.isError
    assert "Figure saved" in result.content[0].text

    # Download the image file from the container
    download_path = workspace["temp_dir"] / "downloaded_plot.png"
    result = await session.call_tool(
        "download_file",
        arguments={
            "relpath": "test_plot.png",
            "local_path": str(download_path),
        },
    )

    assert not result.isError
    assert download_path.exists()

    # Verify it's a valid image
    img = Image.open(download_path)
    # The bbox_inches='tight' option adjusts the size, so just verify it's a reasonable size
    assert img.size[0] > 400 and img.size[0] < 700
    assert img.size[1] > 300 and img.size[1] < 500


@pytest.mark.asyncio(loop_scope="module")
async def test_upload_file(session: ClientSession, mcp_server_workspace):
    """Test uploading a file to the container."""
    workspace = mcp_server_workspace

    # Create a test file
    test_file = workspace["temp_dir"] / "test_upload.txt"
    test_content = "Hello from host!"
    test_file.write_text(test_content)

    # Upload file
    result = await session.call_tool(
        "upload_file",
        arguments={
            "relpath": "uploaded.txt",
            "local_path": str(test_file),
        },
    )

    assert not result.isError
    assert not result.content

    # Verify file exists in container
    result = await session.call_tool(
        "execute_ipython_cell",
        arguments={
            "code": "with open('/app/uploaded.txt', 'r') as f: print(f.read())",
        },
    )

    assert test_content in result.content[0].text


@pytest.mark.asyncio(loop_scope="module")
async def test_download_file(session: ClientSession, mcp_server_workspace):
    """Test downloading a file from the container."""
    workspace = mcp_server_workspace

    # Create a file in the container
    test_content = "Hello from container!"
    result = await session.call_tool(
        "execute_ipython_cell",
        arguments={
            "code": f"with open('/app/test_download.txt', 'w') as f: f.write('{test_content}')",
        },
    )

    # Download file
    download_path = workspace["temp_dir"] / "downloaded.txt"
    result = await session.call_tool(
        "download_file",
        arguments={
            "relpath": "test_download.txt",
            "local_path": str(download_path),
        },
    )

    assert not result.isError
    assert not result.content

    # Verify downloaded content
    assert download_path.exists()
    assert download_path.read_text() == test_content


@pytest.mark.asyncio(loop_scope="module")
async def test_upload_nonexistent_file(session: ClientSession, mcp_server_workspace):
    """Test uploading a non-existent file."""
    workspace = mcp_server_workspace

    # Try to upload non-existent file
    result = await session.call_tool(
        "upload_file",
        arguments={
            "relpath": "test.txt",
            "local_path": str(workspace["temp_dir"] / "nonexistent.txt"),
        },
    )

    assert result.isError
    assert "not found" in result.content[0].text.lower()


@pytest.mark.asyncio(loop_scope="module")
async def test_upload_outside_whitelist(session: ClientSession):
    """Test uploading from outside whitelisted directories."""
    # Try to upload from /etc (not whitelisted)
    result = await session.call_tool(
        "upload_file",
        arguments={
            "relpath": "test.txt",
            "local_path": "/etc/passwd",
        },
    )

    assert result.isError
    assert "not within allowed directories" in result.content[0].text


@pytest.mark.asyncio(loop_scope="module")
async def test_download_outside_whitelist(session: ClientSession):
    """Test downloading to outside whitelisted directories."""
    # Create a file in container
    await session.call_tool(
        "execute_ipython_cell",
        arguments={
            "code": "with open('/app/test.txt', 'w') as f: f.write('test')",
        },
    )

    # Try to download to /etc (not whitelisted)
    result = await session.call_tool(
        "download_file",
        arguments={
            "relpath": "test.txt",
            "local_path": "/etc/test.txt",
        },
    )

    assert result.isError
    assert "not within allowed directories" in result.content[0].text


@pytest.mark.asyncio(loop_scope="module")
async def test_install_package(session: ClientSession):
    """Test installing a Python package."""
    # Install a small package
    result = await session.call_tool(
        "execute_ipython_cell",
        arguments={
            "code": "!pip3 install six",
        },
    )

    assert not result.isError

    # Verify package is installed
    result = await session.call_tool(
        "execute_ipython_cell",
        arguments={
            "code": "import six; print(f'six version: {six.__version__}')",
        },
    )

    assert "six version:" in result.content[0].text


@pytest.mark.asyncio(loop_scope="module")
async def test_install_package_with_version(session: ClientSession):
    """Test installing a package with version specification."""
    # Install package with version
    result = await session.call_tool(
        "execute_ipython_cell",
        arguments={
            "code": "!pip install requests>=2.20",
        },
    )

    assert not result.isError

    # Verify package is installed
    result = await session.call_tool(
        "execute_ipython_cell",
        arguments={
            "code": "import requests; print(f'requests version: {requests.__version__}')",
        },
    )

    assert "requests version:" in result.content[0].text


@pytest.mark.asyncio(loop_scope="module")
async def test_install_invalid_package(session: ClientSession):
    """Test installing a non-existent package."""
    # Try to install non-existent package
    result = await session.call_tool(
        "execute_ipython_cell",
        arguments={
            "code": "!pip install this-package-definitely-does-not-exist-12345",
        },
    )

    assert "Could not find a version" in result.content[0].text


@pytest.fixture(scope="module")
def mcp_server_params_with_firewall(mcp_server_workspace, container_image_user):
    """Server parameters for connecting to MCP server with firewall configuration."""
    workspace = mcp_server_workspace

    return {
        "command": sys.executable,
        "args": [
            "-m",
            "ipybox",
            "mcp",
            "--container-tag",
            container_image_user,  # Use -test container (supports firewall)
            "--allowed-dir",
            str(workspace["temp_dir"]),
            "--allowed-domain",
            "gradion.ai",  # Allow access to gradion.ai
            "--allowed-domain",
            "postman-echo.com",  # Allow access to postman-echo.com for testing
        ],
    }


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def session_with_firewall(mcp_server_params_with_firewall) -> AsyncIterator[ClientSession]:
    """Create an MCP client session with firewall enabled for testing."""
    try:
        async with mcp_client(mcp_server_params_with_firewall) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session
    except Exception:
        pass


@pytest.mark.asyncio(loop_scope="module")
async def test_firewall_allows_permitted_domains(session_with_firewall: ClientSession):
    """Test that firewall allows access to permitted domains."""
    # Test access to allowed domain
    result = await session_with_firewall.call_tool(
        "execute_ipython_cell",
        arguments={
            "code": """
import urllib.request
try:
    request = urllib.request.Request(
        'https://postman-echo.com/get',
        headers={'User-Agent': 'Python/3.0'}
    )
    response = urllib.request.urlopen(request, timeout=5)
    data = response.read().decode('utf-8')
    print("SUCCESS: Access to postman-echo.com allowed")
    print("Response contains 'headers':", "headers" in data.lower())
except Exception as e:
    print(f"ERROR: {e}")
""",
        },
    )

    assert not result.isError
    output = result.content[0].text
    assert "SUCCESS: Access to postman-echo.com allowed" in output
    assert "Response contains 'headers': True" in output


@pytest.mark.asyncio(loop_scope="module")
async def test_firewall_blocks_non_permitted_domains(session_with_firewall: ClientSession):
    """Test that firewall blocks access to non-permitted domains."""
    # Test access to blocked domain
    result = await session_with_firewall.call_tool(
        "execute_ipython_cell",
        arguments={
            "code": """
import urllib.request
try:
    response = urllib.request.urlopen('https://example.com', timeout=2)
    data = response.read().decode('utf-8')
    print("ERROR: Access to example.com should be blocked")
except Exception as e:
    print(f"SUCCESS: Access blocked as expected - {e}")
""",
        },
    )

    assert not result.isError  # The code execution itself should succeed
    output = result.content[0].text
    assert "SUCCESS: Access blocked as expected" in output
    assert "Network is unreachable" in output or "urlopen error" in output


@pytest.mark.asyncio(loop_scope="module")
async def test_get_mcp_server_names_empty(session: ClientSession):
    """Test getting MCP server names when none are registered."""
    # Get server names (should be empty initially)
    result = await session.call_tool("get_mcp_server_names", arguments={})

    assert not result.isError
    # Result should be empty list
    output = result.content[0].text if result.content else ""
    # FastMCP returns either "[]" or an empty string for empty lists
    assert "[]" in output or output.strip() == ""


@pytest.mark.asyncio(loop_scope="module")
async def test_register_and_discover_mcp_servers(session: ClientSession, mcp_server_workspace):
    """Test registering MCP servers and discovering them with get_mcp_server_names."""
    workspace = mcp_server_workspace

    # Get the path to the test MCP server on host
    test_server_path = Path(__file__).parent.parent / "mcp_server.py"

    # Save MCP server script to host filesystem (in allowed temp directory)
    host_server_path = workspace["temp_dir"] / "test_mcp_server.py"
    host_server_path.write_text(test_server_path.read_text())

    # Upload the MCP server script to the container's /app directory
    await session.call_tool(
        "upload_file",
        arguments={
            "relpath": "test_mcp_server.py",
            "local_path": str(host_server_path),
        },
    )

    # Register first MCP server (path is relative to /app in container)
    result = await session.call_tool(
        "register_mcp_server",
        arguments={
            "server_name": "test_server_1",
            "server_params": {
                "command": "python",
                "args": ["/app/test_mcp_server.py", "--transport", "stdio"],
            },
        },
    )

    assert not result.isError
    output = result.content[0].text
    # Should return list of tool names
    assert "tool" in output.lower()

    # Register second MCP server with same server but different name
    result = await session.call_tool(
        "register_mcp_server",
        arguments={
            "server_name": "test_server_2",
            "server_params": {
                "command": "python",
                "args": ["/app/test_mcp_server.py", "--transport", "stdio"],
            },
        },
    )

    assert not result.isError

    # Get list of registered server names
    result = await session.call_tool("get_mcp_server_names", arguments={})

    assert not result.isError
    # Combine all content items in case they're split
    full_output = " ".join(item.text for item in result.content)
    assert "test_server_1" in full_output
    assert "test_server_2" in full_output


@pytest.mark.asyncio(loop_scope="module")
async def test_get_mcp_tool_descriptions(session: ClientSession):
    """Test getting tool descriptions for a registered MCP server."""
    # Get tool descriptions for test_server_1
    result = await session.call_tool(
        "get_mcp_tool_descriptions",
        arguments={
            "server_name": "test_server_1",
        },
    )

    assert not result.isError
    output = result.content[0].text

    # Should contain tool names and their descriptions
    assert "tool" in output.lower()
    # The test server has tool-1, tool_2, and tool_3
    assert "tool" in output


@pytest.mark.asyncio(loop_scope="module")
async def test_get_mcp_tool_sources(session: ClientSession):
    """Test getting Python source code for MCP tools."""
    # Get source code for specific tools (using sanitized names: tool-1 becomes tool_1)
    result = await session.call_tool(
        "get_mcp_tool_sources",
        arguments={
            "server_name": "test_server_1",
            "tool_names": ["tool_1", "tool_2"],
        },
    )

    assert not result.isError
    output = result.content[0].text

    # Should contain Python source code for both tools
    assert "tool_1" in output
    assert "tool_2" in output


@pytest.mark.asyncio(loop_scope="module")
async def test_get_all_mcp_tool_sources(session: ClientSession):
    """Test getting all tool sources when tool_names is None."""
    # Get all tool sources (None means all)
    result = await session.call_tool(
        "get_mcp_tool_sources",
        arguments={
            "server_name": "test_server_1",
        },
    )

    assert not result.isError
    output = result.content[0].text

    # Should contain multiple tools
    assert "tool" in output.lower()


@pytest.mark.asyncio(loop_scope="module")
async def test_use_mcp_tool_from_sources(session: ClientSession):
    """Test that generated MCP tool code can be imported and used."""
    # The tools should already be registered from previous tests
    # Import and use tool-1
    code = """
from mcpgen.test_server_1.tool_1 import run, Params
result = run(params=Params(s="Hello from MCP tool!"))
print(result)
"""

    result = await session.call_tool(
        "execute_ipython_cell",
        arguments={
            "code": code,
        },
    )

    assert not result.isError
    output = result.content[0].text
    assert "Hello from MCP tool!" in output
    assert "You passed to tool 1:" in output


@pytest.mark.asyncio(loop_scope="module")
async def test_use_multiple_mcp_servers(session: ClientSession):
    """Test using tools from different registered MCP servers."""
    # Use tool from test_server_1
    code_1 = """
from mcpgen.test_server_1.tool_2 import run, Params
result1 = run(params=Params(s="Server 1"))
print(f"Result from server 1: {result1}")
"""

    result = await session.call_tool(
        "execute_ipython_cell",
        arguments={
            "code": code_1,
        },
    )

    assert not result.isError
    output = result.content[0].text
    assert "Server 1" in output
    assert "You passed to tool 2:" in output

    # Use tool from test_server_2
    code_2 = """
from mcpgen.test_server_2.tool_2 import run, Params
result2 = run(params=Params(s="Server 2"))
print(f"Result from server 2: {result2}")
"""

    result = await session.call_tool(
        "execute_ipython_cell",
        arguments={
            "code": code_2,
        },
    )

    assert not result.isError
    output = result.content[0].text
    assert "Server 2" in output
    assert "You passed to tool 2:" in output


@pytest.mark.asyncio(loop_scope="module")
async def test_mcp_workflow_discovery_to_usage(session: ClientSession):
    """Test the complete workflow: discover servers, explore tools, and use them."""
    # Step 1: Get list of available servers
    result = await session.call_tool("get_mcp_server_names", arguments={})
    assert not result.isError
    servers_output = " ".join(item.text for item in result.content)
    assert "test_server_1" in servers_output

    # Step 2: Get tool descriptions for a server
    result = await session.call_tool(
        "get_mcp_tool_descriptions",
        arguments={
            "server_name": "test_server_1",
        },
    )
    assert not result.isError
    descriptions_output = result.content[0].text
    assert "tool" in descriptions_output.lower()

    # Step 3: Get source code for a specific tool (use sanitized name tool_1)
    result = await session.call_tool(
        "get_mcp_tool_sources",
        arguments={
            "server_name": "test_server_1",
            "tool_names": ["tool_1"],
        },
    )
    assert not result.isError
    source_output = result.content[0].text
    assert "tool" in source_output.lower()

    # Step 4: Use the tool in execute_ipython_cell
    code = """
from mcpgen.test_server_1.tool_1 import run, Params
result = run(params=Params(s="Complete workflow test"))
print(f"Success: {result}")
"""

    result = await session.call_tool(
        "execute_ipython_cell",
        arguments={
            "code": code,
        },
    )

    assert not result.isError
    output = result.content[0].text
    assert "Complete workflow test" in output
    assert "Success:" in output
