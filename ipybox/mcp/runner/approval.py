import asyncio
import json
import uuid
from functools import partial
from typing import Any, Awaitable, Callable

import websockets
from fastapi import WebSocket, WebSocketDisconnect
from websockets import ClientConnection, ConnectionClosed


class ApprovalRequest:
    def __init__(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict[str, Any],
        respond: Callable[[bool], Awaitable[None]],
    ):
        self.server_name = server_name
        self.tool_name = tool_name
        self.arguments = arguments
        self._respond = respond

    def __str__(self) -> str:
        kwargs_str = ", ".join([f"{k}={repr(v)}" for k, v in self.arguments.items()])
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
                        tool_name=params["tool"],
                        arguments=params["arguments"],
                        respond=partial(self._send, request_id=data["id"]),
                    )
                    await self.callback(approval)

        except ConnectionClosed:
            pass


class ApprovalChannel:
    def __init__(
        self,
        approval_required: bool = False,
        approval_timeout: float = 60,
    ):
        self.approval_required = approval_required
        self.approval_timeout = approval_timeout

        self._websocket: WebSocket | None = None
        self._requests: dict[str, asyncio.Future[bool]] = {}

    @property
    def open(self) -> bool:
        return self._websocket is not None

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self._websocket = websocket

        try:
            while True:
                approval_response = await self._websocket.receive_json()
                await self._handle_approval_response(approval_response)
        except WebSocketDisconnect:
            await self.disconnect()

    async def disconnect(self):
        if self._websocket is not None:
            self._websocket = None
            self._requests.clear()

    async def request(self, server_name: str, tool: str, arguments: dict[str, Any]) -> bool:
        if not self.approval_required:
            return True

        if self._websocket is None:
            raise RuntimeError("Approval channel not connected")

        try:
            async with asyncio.timeout(self.approval_timeout):
                request_id = await self._send_approval_request(server_name, tool, arguments)
                return await self._requests[request_id]
        finally:
            self._requests.pop(request_id, None)

    async def _send_approval_request(self, server_name: str, tool: str, arguments: dict[str, Any]) -> str:
        request_id = str(uuid.uuid4())
        approval_request = {
            "jsonrpc": "2.0",
            "method": "approve",
            "params": {"server_name": server_name, "tool": tool, "arguments": arguments},
            "id": request_id,
        }

        future = asyncio.Future[bool]()
        self._requests[request_id] = future

        await self._websocket.send_json(approval_request)  # type: ignore
        return request_id

    async def _handle_approval_response(self, response: dict[str, Any]):
        request_id = response["id"]
        if future := self._requests.get(request_id, None):
            future.set_result(response["result"])
