import asyncio
import uuid
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect


class ApprovalChannel:
    """Server-side channel for sending tool call approval requests to clients.

    `ApprovalChannel` handles `WebSocket` connections from
    [`ApprovalClient`][ipybox.tool_exec.approval.client.ApprovalClient] instances and
    sends approval requests via JSON-RPC. It is used internally by
    [`ToolServer`][ipybox.tool_exec.server.ToolServer] to enforce tool call approval
    before execution.

    When `approval_required` is `False`, all approval requests are automatically granted.
    When `True`, requests are sent to the connected `ApprovalClient` and the channel waits
    for a response within the configured timeout.
    """

    def __init__(
        self,
        approval_required: bool = False,
        approval_timeout: float = 60,
    ):
        """Initialize an `ApprovalChannel`.

        Args:
            approval_required: Whether approval is required for tool execution.
            approval_timeout: Timeout in seconds for approval requests.
        """
        self.approval_required = approval_required
        self.approval_timeout = approval_timeout

        self._websocket: WebSocket | None = None
        self._requests: dict[str, asyncio.Future[bool]] = {}

    @property
    def open(self) -> bool:
        """Whether an `ApprovalClient` is currently connected."""
        return self._websocket is not None

    async def connect(self, websocket: WebSocket):
        """Accept a `WebSocket` connection and process approval responses.

        This method runs until the `WebSocket` is disconnected.

        Args:
            websocket: The `WebSocket` connection to accept.
        """
        await websocket.accept()
        self._websocket = websocket

        try:
            while True:
                approval_response = await self._websocket.receive_json()
                await self._handle_approval_response(approval_response)
        except WebSocketDisconnect:
            await self.disconnect()

    async def disconnect(self):
        """Disconnect the `WebSocket` and error all pending approval requests."""
        if self._websocket is not None:
            self._websocket = None
            for future in self._requests.values():
                if not future.done():
                    future.set_exception(RuntimeError("Approval channel disconnected"))
            self._requests.clear()

    async def request(self, server_name: str, tool_name: str, tool_args: dict[str, Any]) -> bool:
        """Request approval for a tool call.

        If `approval_required` is False, returns `True` immediately. Otherwise, sends an
        approval request to the connected `ApprovalClient` and waits for a response.

        Args:
            server_name: Name of the MCP server providing the tool.
            tool_name: Name of the tool to execute.
            tool_args: Arguments to pass to the tool.

        Returns:
            `True` if approved, `False` if rejected.

        Raises:
            RuntimeError: If no `ApprovalClient` is connected.
            TimeoutError: If the approval request times out.
        """
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
