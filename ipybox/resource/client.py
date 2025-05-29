import asyncio
import io
import mimetypes
import tarfile
from pathlib import Path
from typing import Any

import aiofiles
import aiohttp


class ConnectionError(Exception):
    """Raised when a connection to a resource server cannot be established."""


class ResourceClient:
    """Context manager for

    - loading the source code of Python modules and generated MCP client functions
      from an [`ExecutionContainer`][ipybox.container.ExecutionContainer].
    - generating Python client functions from MCP server tool metadata and storing
      the generated sources in an [`ExecutionContainer`][ipybox.container.ExecutionContainer].

    Args:
        port: Host port for the container's resource port
        host: Hostname or IP address of the container's host
        connect_retries: Number of connection retries.
        connect_retry_interval: Delay between connection retries in seconds.
    """

    def __init__(
        self,
        port: int,
        host: str = "localhost",
        connect_retries: int = 10,
        connect_retry_interval: float = 1.0,
    ):
        self.port = port
        self.host = host
        self._base_url = f"http://{self.host}:{self.port}"
        self._session: aiohttp.ClientSession = None
        self._connect_retries = connect_retries
        self._connect_retry_interval = connect_retry_interval

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()

    async def connect(self):
        self._session = aiohttp.ClientSession()
        await self._status()

    async def disconnect(self):
        await self._session.close()

    async def _status(self) -> dict[str, str]:
        for _ in range(self._connect_retries):
            try:
                async with self._session.get(f"{self._base_url}/status") as response:
                    response.raise_for_status()
                    return await response.json()
            except Exception:
                await asyncio.sleep(self._connect_retry_interval)
        else:
            raise ConnectionError("Failed to connect to resource server")

    async def generate_mcp_sources(self, relpath: str, server_name: str, server_params: dict[str, Any]) -> list[str]:
        """Generate Python client functions for tools provided by an MCP server.

        One MCP client function is generated per MCP tool from its metadata. The generated function is stored in a
        module named `/app/{relpath}/{server_name}/{tool_name}.py`. Importing this module and calling the function
        invokes the corresponding MCP tool. This works for both `stdio` and `sse` based MCP servers. `stdio` based
        MCP servers are executed inside the container, `sse` based MCP servers are expected to run elsewhere.

        Args:
            relpath: Path relative to the container's `/app` directory.
            server_name: An application-defined name for the MCP server. Must be a valid Python module name.
            server_params: MCP server configuration. `stdio` server configurations must specify at least a `command`
                key, `sse` server configurations must specify at least a `url` key.

        Returns:
            List of tool names provided by the MCP server. Tool names are sanitized to ensure they
                can be used as Python module names.
        """
        url = f"{self._base_url}/mcp/{relpath}/{server_name}"
        async with self._session.put(url, json=server_params) as response:
            response.raise_for_status()
            return await response.json()

    async def get_mcp_sources(self, relpath: str, server_name: str) -> dict[str, str]:
        """Get the source code of generated MCP client functions for given MCP `server_name`.

        Args:
            relpath: Path relative to the container's `/app` directory
            server_name: Application-defined name of an MCP server

        Returns:
            Source code of generated MCP client functions. Keys are tool names, values are generated sources.
        """
        url = f"{self._base_url}/mcp/{relpath}"
        async with self._session.get(url, params={"server_name": server_name}) as response:
            response.raise_for_status()
            return await response.json()

    async def get_module_sources(self, module_names: list[str]) -> dict[str, str]:
        """Get the source code of Python modules on the container's Python path.

        Args:
            module_names: A list of Python module names.

        Returns:
            Source code of Python modules. Keys are module names, values are module sources.
        """
        url = f"{self._base_url}/modules"
        async with self._session.get(url, params={"q": module_names}) as response:
            response.raise_for_status()
            return await response.json()

    async def upload_file(self, relpath: str, local_path: Path) -> None:
        """Upload a file to the container.

        Args:
            relpath: Path relative to the container's `/app` directory
            local_path: Local file path to upload

        Raises:
            FileNotFoundError: If the local file doesn't exist
            HTTPError: If the upload fails
        """
        if not local_path.exists() or not local_path.is_file():
            raise FileNotFoundError(f"Local file not found: {local_path}")

        # Determine MIME type
        mime_type, _ = mimetypes.guess_type(str(local_path))
        headers = {"Content-Type": mime_type} if mime_type else {}

        # Read and upload file
        async with aiofiles.open(local_path, mode="rb") as f:
            content = await f.read()

        url = f"{self._base_url}/files/{relpath}"
        async with self._session.post(url, data=content, headers=headers) as response:
            response.raise_for_status()

    async def download_file(self, relpath: str, local_path: Path) -> None:
        """Download a file from the container.

        Args:
            relpath: Path relative to the container's `/app` directory
            local_path: Local file path to save to

        Raises:
            HTTPError: If the file doesn't exist or download fails
        """
        # Create parent directories if needed
        local_path.parent.mkdir(parents=True, exist_ok=True)

        url = f"{self._base_url}/files/{relpath}"
        async with self._session.get(url) as response:
            response.raise_for_status()

            # Stream content to file
            async with aiofiles.open(local_path, mode="wb") as f:
                async for chunk in response.content.iter_chunked(1024 * 1024):  # 1MB chunks
                    await f.write(chunk)

    async def delete_file(self, relpath: str) -> None:
        """Delete a file from the container.

        Args:
            relpath: Path relative to the container's `/app` directory

        Raises:
            HTTPError: If the file doesn't exist or deletion fails
        """
        url = f"{self._base_url}/files/{relpath}"
        async with self._session.delete(url) as response:
            response.raise_for_status()

    async def upload_directory(self, relpath: str, local_path: Path) -> None:
        """Upload a directory to the container as a tar archive.

        Args:
            relpath: Path relative to the container's `/app` directory
            local_path: Local directory path to upload

        Raises:
            FileNotFoundError: If the local directory doesn't exist
            HTTPError: If the upload fails
        """
        if not local_path.exists() or not local_path.is_dir():
            raise FileNotFoundError(f"Local directory not found: {local_path}")

        # Create tar archive in memory
        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode="w:gz") as tar:
            # Add directory contents to archive
            for item in local_path.rglob("*"):
                if item.is_file():
                    # Calculate relative path for archive
                    arcname = item.relative_to(local_path)
                    tar.add(item, arcname=str(arcname))

        # Upload tar archive
        tar_buffer.seek(0)
        url = f"{self._base_url}/directories/{relpath}"
        headers = {"Content-Type": "application/x-gzip"}
        async with self._session.post(url, data=tar_buffer.getvalue(), headers=headers) as response:
            response.raise_for_status()

    async def download_directory(self, relpath: str, local_path: Path) -> None:
        """Download a directory from the container as a tar archive.

        Args:
            relpath: Path relative to the container's `/app` directory
            local_path: Local directory path to extract to

        Raises:
            HTTPError: If the directory doesn't exist or download fails
        """
        # Create target directory
        local_path.mkdir(parents=True, exist_ok=True)

        url = f"{self._base_url}/directories/{relpath}"
        async with self._session.get(url) as response:
            response.raise_for_status()

            # Download tar content
            content = await response.read()

            # Extract tar archive
            with io.BytesIO(content) as tar_buffer:
                with tarfile.open(fileobj=tar_buffer, mode="r:gz") as tar:
                    # Extract all files
                    tar.extractall(path=local_path)
