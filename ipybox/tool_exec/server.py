import argparse
import asyncio
import copy
from contextlib import AsyncExitStack
from typing import Any

import aiohttp
import uvicorn
import uvicorn.config
from fastapi import FastAPI, WebSocket
from pydantic import BaseModel

from ipybox.mcp_client import MCPClient
from ipybox.tool_exec.approval.server import ApprovalChannel


class ToolCall(BaseModel):
    server_name: str
    server_params: dict[str, Any]
    tool_name: str
    tool_args: dict[str, Any]


class ToolServer:
    """HTTP server that manages MCP servers and executes their tools with optional approval.

    ToolServer provides HTTP endpoints for executing MCP tools and a WebSocket endpoint
    for sending approval requests to clients. MCP servers are started on demand when tools
    are first executed and cached for subsequent calls.

    Endpoints:

    - `PUT /reset`: Closes all started MCP servers
    - `POST /run`: Executes an MCP tool (with optional approval)
    - `WS /approval`: WebSocket endpoint for
        [`ApprovalClient`][ipybox.tool_exec.approval.client.ApprovalClient] connections

    Example:
        ```python
        async with ToolServer(approval_required=True) as server:
            async with ApprovalClient(callback=on_approval_request):
                # Execute code that calls MCP tools
                ...
        ```
    """

    def __init__(
        self,
        host="localhost",
        port: int = 8900,
        approval_required: bool = False,
        approval_timeout: float | None = None,
        connect_timeout: float = 30,
        log_to_stderr: bool = False,
        log_level: str = "INFO",
    ):
        """
        Args:
            host: Hostname the server binds to.
            port: Port number the server listens on.
            approval_required: Whether tool calls require approval.
            approval_timeout: Timeout in seconds for approval requests. If `None`,
                no timeout is applied.
            connect_timeout: Timeout in seconds for starting MCP servers.
            log_to_stderr: Whether to log to stderr instead of stdout.
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        """
        self.host = host
        self.port = port

        self.approval_timeout = approval_timeout
        self.connect_timeout = connect_timeout

        self.log_to_stderr = log_to_stderr
        self.log_level = log_level

        self.ready_checks: int = 50
        self.ready_check_interval: float = 0.2

        self.app = FastAPI(title="MCP tool runner")
        self.app.websocket("/approval")(self.approval)
        self.app.get("/status")(self.status)
        self.app.put("/reset")(self.reset)
        self.app.post("/run", response_model=None)(self.run)

        self._server: uvicorn.Server | None = None
        self._server_task: asyncio.Task | None = None
        self._approval_channel: ApprovalChannel = ApprovalChannel(
            approval_required=approval_required,
            approval_timeout=approval_timeout,
        )

        self._mcp_client_lifecycle_lock = asyncio.Lock()
        self._mcp_client_exit_stack: AsyncExitStack = AsyncExitStack()
        self._mcp_clients: dict[str, MCPClient] = {}

    async def approval(self, websocket: WebSocket):
        if self._approval_channel.open:
            try:
                await self._approval_channel.join()
            except asyncio.TimeoutError:
                message = "Timed out waiting for previous connection to close"
                await websocket.close(code=1008, reason=message)
                return

        await self._approval_channel.connect(websocket)

    async def status(self):
        return {"status": "ok"}

    async def reset(self):
        await self._close_mcp_clients()
        return {"reset": "success"}

    async def run(self, call: ToolCall) -> dict[str, Any] | str | None:
        try:
            if not await self._approval_channel.request(call.server_name, call.tool_name, call.tool_args):
                return {"error": f"Approval request for {call.server_name}.{call.tool_name} rejected"}
        except asyncio.TimeoutError:
            return {"error": f"Approval request for {call.server_name}.{call.tool_name} expired"}
        except Exception as e:
            return {"error": f"Approval request for {call.server_name}.{call.tool_name} failed: {str(e)}"}

        try:
            client = await self._get_mcp_client(
                call.server_name,
                call.server_params,
            )
            result = await client.run(
                call.tool_name,
                call.tool_args,
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
        """Start the HTTP server.

        Raises:
            RuntimeError: If the server is already running.
        """
        if self._server_task is not None:
            raise RuntimeError("Server already running")

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
            ws="wsproto",
        )

        self._server = uvicorn.Server(config)
        self._server_task = asyncio.create_task(self._server.serve())

        await self._ready()

    async def stop(self):
        """Stop the HTTP server and close all managed MCP servers."""
        if self._server_task is None:
            return

        await self._close_mcp_clients()
        await self._approval_channel.disconnect()

        if self._server is not None:
            self._server.should_exit = True

        await self.join()

        self._server_task = None
        self._server = None

    async def join(self):
        """Wait for the HTTP server task to stop."""
        if self._server_task is not None:
            try:
                await self._server_task
            except asyncio.CancelledError:
                pass

    async def _get_mcp_client(self, server_name: str, server_params: dict[str, Any]) -> MCPClient:
        async with self._mcp_client_lifecycle_lock:
            if server_name not in self._mcp_clients:
                client = MCPClient(server_params)
                client = await self._mcp_client_exit_stack.enter_async_context(client)
                self._mcp_clients[server_name] = client
            return self._mcp_clients[server_name]

    async def _close_mcp_clients(self):
        async with self._mcp_client_lifecycle_lock:
            await self._mcp_client_exit_stack.aclose()
            self._mcp_client_exit_stack = AsyncExitStack()
            self._mcp_clients.clear()

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
