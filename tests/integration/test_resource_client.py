import shutil
import tempfile
from pathlib import Path

import pytest

from ipybox import ResourceClient
from tests.mcp_server import STDIO_SERVER_PATH


@pytest.mark.asyncio
async def test_get_module_source(resource_client: ResourceClient):
    # Get the source through the resource server
    result = await resource_client.get_module_sources(["ipybox.modinfo"])
    source = result["ipybox.modinfo"]

    # Load the actual source file
    modinfo_path = Path("ipybox", "modinfo.py")
    with open(modinfo_path) as f:
        actual_source = f.read()

    assert source == actual_source


@pytest.mark.asyncio
async def test_generate_and_get_mcp_sources(resource_client: ResourceClient, workspace: str, server_params: dict):
    if "command" in server_params:
        # Copy MCP server to /app/workspace/mcp_server.py in the container
        shutil.copy(STDIO_SERVER_PATH, Path(workspace) / "mcp_server.py")
        server_params["args"] = ["workspace/mcp_server.py"]

    # generate MCP client sources in /app/mcpgen/test
    gen_result = await resource_client.generate_mcp_sources(
        relpath="mcpgen", server_name="test", server_params=server_params
    )
    assert gen_result == ["tool_1", "tool_2"]

    # retrieve the generated sources via ipybox filesystem
    get_result_1 = await resource_client.get_mcp_sources(relpath="mcpgen", server_name="test")

    module_name_1 = "mcpgen.test.tool_1"
    module_name_2 = "mcpgen.test.tool_2"

    # get the generated sources via ipybox module loading
    get_result_2 = await resource_client.get_module_sources([module_name_1, module_name_2])

    source_1 = get_result_1["tool_1"]
    source_2 = get_result_1["tool_2"]

    # check if retrieval mechanisms are equivalent
    assert source_1 == get_result_2[module_name_1]
    assert source_2 == get_result_2[module_name_2]

    # check if it contains the generated function signature
    assert "tool_1(params: Params)" in source_1
    assert "tool_2(params: Params)" in source_2


@pytest.mark.asyncio
async def test_file_upload_download(resource_client: ResourceClient):
    """Test uploading and downloading files."""
    # Create a temporary file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("Hello, world!")
        local_file = Path(f.name)

    try:
        # Upload file
        await resource_client.upload_file("test/hello.txt", local_file)

        # Download file to a different location
        with tempfile.TemporaryDirectory() as tmpdir:
            download_path = Path(tmpdir) / "downloaded.txt"
            await resource_client.download_file("test/hello.txt", download_path)

            # Verify content
            assert download_path.read_text() == "Hello, world!"
    finally:
        local_file.unlink()


@pytest.mark.asyncio
async def test_file_upload_creates_directories(resource_client: ResourceClient):
    """Test that uploading a file creates parent directories."""
    # Create a temporary file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("Nested file content")
        local_file = Path(f.name)

    try:
        # Upload file to nested path
        await resource_client.upload_file("deeply/nested/path/file.txt", local_file)

        # Download and verify
        with tempfile.TemporaryDirectory() as tmpdir:
            download_path = Path(tmpdir) / "downloaded.txt"
            await resource_client.download_file("deeply/nested/path/file.txt", download_path)
            assert download_path.read_text() == "Nested file content"
    finally:
        local_file.unlink()


@pytest.mark.asyncio
async def test_file_delete(resource_client: ResourceClient):
    """Test deleting files."""
    # Create and upload a file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("To be deleted")
        local_file = Path(f.name)

    try:
        await resource_client.upload_file("delete_me.txt", local_file)

        # Delete the file
        await resource_client.delete_file("delete_me.txt")

        # Verify file is gone by trying to download it
        with tempfile.TemporaryDirectory() as tmpdir:
            download_path = Path(tmpdir) / "should_fail.txt"
            with pytest.raises(Exception):  # Should raise HTTPError
                await resource_client.download_file("delete_me.txt", download_path)
    finally:
        local_file.unlink()


@pytest.mark.asyncio
async def test_directory_upload_download(resource_client: ResourceClient):
    """Test uploading and downloading directories."""
    # Create a temporary directory with some files
    with tempfile.TemporaryDirectory() as tmpdir:
        source_dir = Path(tmpdir) / "source"
        source_dir.mkdir()

        # Create some files
        (source_dir / "file1.txt").write_text("File 1 content")
        (source_dir / "file2.txt").write_text("File 2 content")
        (source_dir / "subdir").mkdir()
        (source_dir / "subdir" / "file3.txt").write_text("File 3 content")

        # Upload directory
        await resource_client.upload_directory("test_dir", source_dir)

        # Download directory to a different location
        download_dir = Path(tmpdir) / "downloaded"
        await resource_client.download_directory("test_dir", download_dir)

        # Verify contents
        assert (download_dir / "file1.txt").read_text() == "File 1 content"
        assert (download_dir / "file2.txt").read_text() == "File 2 content"
        assert (download_dir / "subdir" / "file3.txt").read_text() == "File 3 content"


@pytest.mark.asyncio
async def test_binary_file_upload_download(resource_client: ResourceClient):
    """Test uploading and downloading binary files."""
    # Create a binary file
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".bin", delete=False) as f:
        binary_data = bytes(range(256))
        f.write(binary_data)
        local_file = Path(f.name)

    try:
        # Upload binary file
        await resource_client.upload_file("binary/test.bin", local_file)

        # Download and verify
        with tempfile.TemporaryDirectory() as tmpdir:
            download_path = Path(tmpdir) / "downloaded.bin"
            await resource_client.download_file("binary/test.bin", download_path)
            assert download_path.read_bytes() == binary_data
    finally:
        local_file.unlink()


@pytest.mark.asyncio
async def test_file_not_found_errors(resource_client: ResourceClient):
    """Test proper error handling for non-existent files."""
    # Try to download non-existent file
    with tempfile.TemporaryDirectory() as tmpdir:
        download_path = Path(tmpdir) / "should_fail.txt"
        with pytest.raises(Exception):  # Should raise HTTPError
            await resource_client.download_file("does_not_exist.txt", download_path)

    # Try to delete non-existent file
    with pytest.raises(Exception):  # Should raise HTTPError
        await resource_client.delete_file("does_not_exist.txt")

    # Try to download non-existent directory
    with tempfile.TemporaryDirectory() as tmpdir:
        download_dir = Path(tmpdir) / "should_fail"
        with pytest.raises(Exception):  # Should raise HTTPError
            await resource_client.download_directory("does_not_exist", download_dir)


@pytest.mark.asyncio
async def test_upload_local_file_not_found(resource_client: ResourceClient):
    """Test proper error handling when local file doesn't exist."""
    # Try to upload non-existent file
    with pytest.raises(FileNotFoundError):
        await resource_client.upload_file("test.txt", Path("/does/not/exist.txt"))

    # Try to upload non-existent directory
    with pytest.raises(FileNotFoundError):
        await resource_client.upload_directory("test_dir", Path("/does/not/exist"))
