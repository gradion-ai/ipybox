import asyncio
import json
from functools import partial
from typing import Any, Awaitable, Callable

import websockets
from websockets import ClientConnection, ConnectionClosed


class ApprovalRequest:
    def __init__(
        self,
        server_name: str,
        tool_name: str,
        tool_args: dict[str, Any],
        respond: Callable[[bool], Awaitable[None]],
    ):
        self.server_name = server_name
        self.tool_name = tool_name
        self.tool_args = tool_args
        self._respond = respond

    def __str__(self) -> str:
        kwargs_str = ", ".join([f"{k}={repr(v)}" for k, v in self.tool_args.items()])
        return f"{self.server_name}.{self.tool_name}({kwargs_str})"

    async def reject(self) -> bool:
        return await self.respond(False)

    async def approve(self) -> bool:
        return await self.respond(True)

    async def respond(self, result: bool):
        await self._respond(result)


ApprovalCallback = Callable[[ApprovalRequest], Awaitable[None]]


class ApprovalClient:
    def __init__(
        self,
        callback: ApprovalCallback,
        host: str = "localhost",
        port: int = 8900,
    ):
        self.callback = callback
        self.host = host
        self.port = port

        self._uri = f"ws://{host}:{port}/approval"
        self._conn: ClientConnection | None = None
        self._task: asyncio.Task | None = None

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()

    async def connect(self):
        self._conn = await websockets.connect(self._uri)
        self._task = asyncio.create_task(self._recv())

    async def disconnect(self):
        if self._conn:
            await self._conn.close()
            self._conn = None
        if self._task:
            await self._task
            self._task = None

    async def _send(self, result: bool, request_id: str):
        if not self._conn:
            raise RuntimeError("Not connected")

        response = {
            "jsonrpc": "2.0",
            "result": result,
            "id": request_id,
        }
        await self._conn.send(json.dumps(response))

    async def _recv(self):
        if not self._conn:
            raise RuntimeError("Not connected")

        try:
            async for msg in self._conn:
                data = json.loads(msg)

                if data.get("method") == "approve":
                    params = data.get("params", {})
                    approval = ApprovalRequest(
                        server_name=params["server_name"],
                        tool_name=params["tool_name"],
                        tool_args=params["tool_args"],
                        respond=partial(self._send, request_id=data["id"]),
                    )
                    await self.callback(approval)

        except ConnectionClosed:
            pass
