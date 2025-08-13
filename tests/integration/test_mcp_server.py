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
