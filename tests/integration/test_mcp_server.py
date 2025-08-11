"""Integration tests for the ipybox MCP server."""

import json
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

        # Create subdirectories
        images_dir = temp_path / "images"
        images_dir.mkdir()

        yield {
            "temp_dir": temp_path,
            "images_dir": images_dir,
        }


@pytest.fixture(scope="module")
def mcp_server_params(mcp_server_workspace):
    """Server parameters for connecting to MCP server."""
    workspace = mcp_server_workspace

    return {
        "command": sys.executable,
        "args": [
            "-m",
            "ipybox.mcp.server",
            "--allowed-dirs",
            str(workspace["temp_dir"]),
            str(Path.home()),
            "--images-dir",
            str(workspace["images_dir"]),
        ],
    }


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def session(mcp_server_params, container_image_root) -> AsyncIterator[ClientSession]:
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
    content = json.loads(result.content[0].text)
    assert "before_reset" in content["text"]

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
    content = json.loads(result.content[0].text)
    assert "Variable not defined" in content["text"]


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
    content = json.loads(result.content[0].text)

    assert "text" in content
    assert "Hello, World!" in content["text"]
    assert "Result: 4" in content["text"]
    assert content["images"] == []


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

    content = json.loads(result.content[0].text)
    assert "x = 42" in content["text"]


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

    # First install Pillow
    await session.call_tool(
        "execute_ipython_cell",
        arguments={
            "code": "!pip install pillow",
        },
    )

    # Generate an image
    code = """
from PIL import Image, ImageDraw

# Create a simple image
img = Image.new('RGB', (100, 100), color='red')
draw = ImageDraw.Draw(img)
draw.rectangle([25, 25, 75, 75], fill='blue')

img  # Display the image
"""

    result = await session.call_tool(
        "execute_ipython_cell",
        arguments={
            "code": code,
            "images_dir": str(workspace["images_dir"]),
        },
    )

    assert not result.isError
    content = json.loads(result.content[0].text)

    assert "images" in content
    assert len(content["images"]) == 1

    # Verify image was saved
    image_path = Path(content["images"][0])
    assert image_path.exists()
    assert image_path.parent == workspace["images_dir"]

    # Verify it's a valid image
    img = Image.open(image_path)
    assert img.size == (100, 100)


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

    content = json.loads(result.content[0].text)
    assert test_content in content["text"]


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
    content = json.loads(result.content[0].text)

    # Verify package is installed
    result = await session.call_tool(
        "execute_ipython_cell",
        arguments={
            "code": "import six; print(f'six version: {six.__version__}')",
        },
    )

    content = json.loads(result.content[0].text)
    assert "six version:" in content["text"]


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

    content = json.loads(result.content[0].text)
    assert "requests version:" in content["text"]


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
