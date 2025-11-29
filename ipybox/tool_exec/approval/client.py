import asyncio
import json
import logging
from functools import partial
from typing import Any, Awaitable, Callable

import websockets
from websockets import ClientConnection, ConnectionClosed

logger = logging.getLogger(__name__)


class ApprovalRequest:
    """Represents a tool call approval request.

    `ApprovalRequest` instances are passed to the approval callback registered with
    [`ApprovalClient`][ipybox.tool_exec.approval.client.ApprovalClient]. The callback
    must call [`approve`][ipybox.tool_exec.approval.client.ApprovalRequest.approve]
    or [`reject`][ipybox.tool_exec.approval.client.ApprovalRequest.reject] to send
    the approval decision back to the server.

    Example:
        ```python
        async def on_approval(request: ApprovalRequest):
            print(f"Approval request: {request}")
            if request.tool_name == "dangerous_tool":
                await request.reject()
            else:
                await request.approve()
        ```
    """

    def __init__(
        self,
        server_name: str,
        tool_name: str,
        tool_args: dict[str, Any],
        respond: Callable[[bool], Awaitable[None]],
    ):
        """Initialize an `ApprovalRequest`.

        Args:
            server_name: Name of the MCP server providing the tool.
            tool_name: Name of the tool to execute.
            tool_args: Arguments to pass to the tool.
            respond: Callback to send the approval decision.
        """
        self.server_name = server_name
        self.tool_name = tool_name
        self.tool_args = tool_args
        self._respond = respond

    def __str__(self) -> str:
        kwargs_str = ", ".join([f"{k}={repr(v)}" for k, v in self.tool_args.items()])
        return f"{self.server_name}.{self.tool_name}({kwargs_str})"

    async def reject(self):
        """Reject the approval request."""
        return await self._respond(False)

    async def approve(self):
        """Approve the approval request."""
        return await self._respond(True)


ApprovalCallback = Callable[[ApprovalRequest], Awaitable[None]]
"""Type alias for approval callback functions.

An approval callback is an async function that receives an
[`ApprovalRequest`][ipybox.tool_exec.approval.client.ApprovalRequest] and must call
one of its response methods (`approve()` or `reject()`) to send the decision back to
the server.
"""


class ApprovalClient:
    """Client for handling tool call approval requests.

    `ApprovalClient` connects to a [`ToolServer`][ipybox.tool_exec.server.ToolServer]'s
    [`ApprovalChannel`][ipybox.tool_exec.approval.server.ApprovalChannel] and receives
    approval requests. Each request is passed to the registered callback, which must
    approve or reject the request.

    Example:
        ```python
        async def on_approval(request: ApprovalRequest):
            print(f"Approval request: {request}")
            await request.approve()

        async with ApprovalClient(callback=on_approval):
            # Execute code that triggers MCP tool calls
            ...
        ```
    """

    def __init__(
        self,
        callback: ApprovalCallback,
        host: str = "localhost",
        port: int = 8900,
    ):
        """Initialize an `ApprovalClient`.

        Args:
            callback: Async function called for each approval request.
            host: Hostname of the `ToolServer`.
            port: Port number of the `ToolServer`.
        """
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
        """Connect to a `ToolServer`'s `ApprovalChannel`."""
        self._conn = await websockets.connect(self._uri)
        self._task = asyncio.create_task(self._recv())

    async def disconnect(self):
        """Disconnect from the `ToolServer`'s `ApprovalChannel`."""
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
                    try:
                        await self.callback(approval)
                    except Exception:
                        logger.exception("Error in approval callback")

        except ConnectionClosed:
            pass
