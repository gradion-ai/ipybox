from typing import Any

import aiohttp
import requests
from pydantic_core import to_jsonable_python


class ToolRunnerError(Exception):
    """Raised when tool execution fails on the server or when approval is rejected."""


class ToolRunner:
    """Client for executing MCP tools on a [`ToolServer`][ipybox.tool_exec.server.ToolServer].

    Example:
        ```python
        runner = ToolRunner(
            server_name="fetch",
            server_params={"command": "uvx", "args": ["mcp-server-fetch"]},
        )
        result = await runner.run("fetch", {"url": "https://example.com"})
        ```
    """

    def __init__(
        self,
        server_name: str,
        server_params: dict[str, Any],
        host: str = "localhost",
        port: int = 8900,
    ):
        """
        Args:
            server_name: Name of the MCP server.
            server_params: MCP server parameters.
            host: Hostname of the `ToolServer`.
            port: Port number of the `ToolServer`.
        """
        self.server_name = server_name
        self.server_params = server_params

        self.host = host
        self.port = port

        self.url = f"http://{host}:{port}/run"

    async def reset(self):
        """Reset the `ToolServer`, stopping all started MCP servers."""
        await reset(host=self.host, port=self.port)

    async def run(self, tool_name: str, tool_args: dict[str, Any]) -> dict[str, Any] | str | None:
        """Execute a tool on the configured MCP server.

        Args:
            tool_name: Name of the tool to execute.
            tool_args: Arguments to pass to the tool.

        Returns:
            The tool execution result.

        Raises:
            ToolRunnerError: If tool execution fails or approval is denied.
        """
        async with aiohttp.ClientSession() as session:
            async with session.post(url=self.url, json=self._create_input_data(tool_name, tool_args)) as response:
                response.raise_for_status()
                response_json = await response.json()

                if "error" in response_json:
                    raise ToolRunnerError(response_json["error"])

                return response_json["result"]

    def run_sync(self, tool_name: str, tool_args: dict[str, Any]) -> dict[str, Any] | str | None:
        """Synchronous version of [`run`][ipybox.tool_exec.client.ToolRunner.run].

        Args:
            tool_name: Name of the tool to execute.
            tool_args: Arguments to pass to the tool.

        Returns:
            The tool execution result.

        Raises:
            ToolRunnerError: If tool execution fails or approval is denied.
        """
        response = requests.post(url=self.url, json=self._create_input_data(tool_name, tool_args))
        response.raise_for_status()
        response_json = response.json()

        if "error" in response_json:
            raise ToolRunnerError(response_json["error"])

        return response_json["result"]

    def _create_input_data(self, tool_name: str, tool_args: dict[str, Any]) -> dict[str, Any]:
        return {
            "server_name": self.server_name,
            "server_params": self.server_params,
            "tool_name": tool_name,
            "tool_args": to_jsonable_python(tool_args),
        }


async def reset(host: str = "localhost", port: int = 8900):
    """Reset a `ToolServer`, stopping all started MCP servers.

    Args:
        host: Hostname of the `ToolServer`.
        port: Port number of the `ToolServer`.
    """
    async with aiohttp.ClientSession() as session:
        async with session.put(url=f"http://{host}:{port}/reset") as response:
            response.raise_for_status()
