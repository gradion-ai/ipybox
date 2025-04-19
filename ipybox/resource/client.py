import asyncio
from typing import Any

import aiohttp


class ConnectionError(Exception):
    """Exception raised when connection to the resource server fails."""

    pass


class ResourceClient:
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
        """Generate MCP client code from MCP `server_params`.

        The generated code will be stored in `/app/{relpath}/{server_name}/{tool_name}.py`
        in the container for each tool provided by the server.

        Args:
            relpath: Path relative to the container's `/app` directory.
            server_name: An application-defined name for the MCP server.
            server_params: MCP server paramaters. A `stdio` based MCP server requires
                a `command` key, an `sse` based MCP server requires a `url` key.

        Returns:
            List of (sanitized) tool names. Tool names are sanitized to
                ensure they can be used as Python module names.
        """
        url = f"{self._base_url}/mcp/{relpath}/{server_name}"
        async with self._session.put(url, json=server_params) as response:
            response.raise_for_status()
            return await response.json()

    async def get_mcp_sources(self, relpath: str, server_name: str) -> dict[str, str]:
        """Get generated MCP client code for a given MCP server.

        Args:
            relpath: Path relative to the container's `/app` directory.
            server_name: An application-defined name for the MCP server.

        Returns:
            Dictionary of tool names and their corresponding source code.
        """
        url = f"{self._base_url}/mcp/{relpath}"
        async with self._session.get(url, params={"server_name": server_name}) as response:
            response.raise_for_status()
            return await response.json()

    async def get_module_sources(self, module_names: list[str]) -> dict[str, str]:
        """Get source code for Python modules.

        Args:
            module_names: List of module names to get source code for.

        Returns:
            Dictionary of module names and their corresponding source code.
        """
        url = f"{self._base_url}/modules"
        async with self._session.get(url, params={"q": module_names}) as response:
            response.raise_for_status()
            return await response.json()
