from typing import Any

import aiohttp
import requests


class ToolRunnerError(Exception):
    pass


class ToolRunner:
    def __init__(
        self,
        server_name: str,
        server_params: dict[str, Any],
        host: str = "localhost",
        port: int = 8900,
    ):
        self.server_name = server_name
        self.server_params = server_params

        self.host = host
        self.port = port

        self.url = f"http://{host}:{port}/run"

    async def reset(self):
        await reset(host=self.host, port=self.port)

    async def run(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any] | str | None:
        async with aiohttp.ClientSession() as session:
            async with session.post(url=self.url, json=self._create_input_data(tool, arguments)) as response:
                response.raise_for_status()
                response_json = await response.json()

                if "error" in response_json:
                    raise ToolRunnerError(response_json["error"])

                return response_json["result"]

    def run_sync(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any] | str | None:
        response = requests.post(url=self.url, json=self._create_input_data(tool, arguments))
        response.raise_for_status()
        response_json = response.json()

        if "error" in response_json:
            raise ToolRunnerError(response_json["error"])

        return response_json["result"]

    def _create_input_data(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return {
            "server_name": self.server_name,
            "server_params": self.server_params,
            "tool": tool,
            "arguments": arguments,
        }


async def reset(host: str = "localhost", port: int = 8900):
    async with aiohttp.ClientSession() as session:
        async with session.put(url=f"http://{host}:{port}/reset") as response:
            response.raise_for_status()
