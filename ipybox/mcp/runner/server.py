import argparse
import asyncio
import copy
from contextlib import AsyncExitStack
from typing import Any

import aiohttp
import uvicorn
import uvicorn.config
from fastapi import FastAPI
from pydantic import BaseModel

from ipybox.mcp.client import MCPClient


class ToolRunRequest(BaseModel):
    server_name: str
    server_params: dict[str, Any]
    tool: str
    arguments: dict[str, Any]


class ToolServer:
    def __init__(
        self,
        host="localhost",
        port: int = 8900,
        connect_timeout: float = 5,
        log_to_stderr: bool = False,
        log_level: str = "INFO",
    ):
        self.host = host
        self.port = port
        self.connect_timeout = connect_timeout
        self.log_to_stderr = log_to_stderr
        self.log_level = log_level

        self.ready_checks: int = 50
        self.ready_check_interval: float = 0.2

        self.app = FastAPI(title="MCP tool runner")
        self.app.get("/status")(self.status)
        self.app.post("/run", response_model=None)(self.run)
        self.app.put("/reset")(self.reset)

        self._task: asyncio.Task | None = None
        self._server: uvicorn.Server | None = None

        self._stack: AsyncExitStack = AsyncExitStack()
        self._clients: dict[str, MCPClient] = {}
        self._lock = asyncio.Lock()

    async def status(self):
        return {"status": "ok"}

    async def reset(self):
        await self._close_mcp_clients()
        return {"reset": "success"}

    async def run(self, request: ToolRunRequest) -> dict[str, Any] | str | None:
        try:
            client = await self._get_mcp_client(
                request.server_name,
                request.server_params,
            )
            result = await client.run(
                request.tool,
                request.arguments,
            )
        except Exception as e:
            return {"error": str(e)}
        else:
            return {"result": result}

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.stop()

    async def start(self):
        if self._task is not None:
            raise RuntimeError("Server is already running")

        LOGGING_CONFIG = uvicorn.config.LOGGING_CONFIG

        if self.log_to_stderr:
            LOGGING_CONFIG = copy.deepcopy(LOGGING_CONFIG)
            LOGGING_CONFIG["handlers"]["default"]["stream"] = "ext://sys.stderr"
            LOGGING_CONFIG["handlers"]["access"]["stream"] = "ext://sys.stderr"

        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            log_config=LOGGING_CONFIG,
            log_level=self.log_level.lower(),
        )

        self._server = uvicorn.Server(config)
        self._task = asyncio.create_task(self._server.serve())

        await self._ready()

    async def stop(self):
        if self._task is None:
            return

        await self._close_mcp_clients()

        if self._server is not None:
            self._server.should_exit = True

        await self.join()

        self._task = None
        self._server = None

    async def join(self):
        if self._task is not None:
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _get_mcp_client(self, server_name: str, server_params: dict[str, Any]) -> MCPClient:
        async with self._lock:
            if server_name not in self._clients:
                client = MCPClient(server_params)
                client = await self._stack.enter_async_context(client)
                self._clients[server_name] = client
            return self._clients[server_name]

    async def _close_mcp_clients(self):
        async with self._lock:
            await self._stack.aclose()
            self._stack = AsyncExitStack()
            self._clients.clear()

    async def _ready(self):
        status_url = f"http://{self.host}:{self.port}/status"

        async with aiohttp.ClientSession() as session:
            for _ in range(self.ready_checks):
                try:
                    async with session.get(status_url) as response:
                        response.raise_for_status()
                        break
                except Exception:
                    await asyncio.sleep(self.ready_check_interval)
            else:
                raise RuntimeError("Server not ready")


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=str, default="localhost")
    parser.add_argument("--port", type=int, default=8900)
    parser.add_argument("--log-level", type=str, default="INFO")
    args = parser.parse_args()

    async with ToolServer(
        host=args.host,
        port=args.port,
        log_level=args.log_level,
    ) as server:
        await server.join()


if __name__ == "__main__":
    asyncio.run(main())
