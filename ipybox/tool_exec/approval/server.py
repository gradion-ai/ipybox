import asyncio
import uuid
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect


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
            for future in self._requests.values():
                if not future.done():
                    future.cancel()
            self._requests.clear()

    async def request(self, server_name: str, tool_name: str, tool_args: dict[str, Any]) -> bool:
        if not self.approval_required:
            return True

        if self._websocket is None:
            raise RuntimeError("Approval channel not connected")

        request_id: str | None = None

        try:
            async with asyncio.timeout(self.approval_timeout):
                request_id = await self._send_approval_request(server_name, tool_name, tool_args)
                return await self._requests[request_id]
        finally:
            if request_id is not None:
                self._requests.pop(request_id, None)

    async def _send_approval_request(self, server_name: str, tool_name: str, tool_args: dict[str, Any]) -> str:
        request_id = str(uuid.uuid4())
        approval_request = {
            "jsonrpc": "2.0",
            "method": "approve",
            "params": {"server_name": server_name, "tool_name": tool_name, "tool_args": tool_args},
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
