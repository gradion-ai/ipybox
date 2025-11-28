"""Internal IPython kernel client implementation.

This module is not part of the public API. Applications should use the
[`CodeExecutor`][ipybox.CodeExecutor] facade instead.
"""

import asyncio
import logging
from base64 import b64decode
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator
from uuid import uuid4

import aiofiles
import aiohttp
from tornado.escape import json_decode, json_encode
from tornado.httpclient import HTTPRequest
from tornado.websocket import WebSocketClientConnection, websocket_connect

logger = logging.getLogger(__name__)


class ExecutionError(Exception):
    """Raised when code executed in an IPython kernel raises an error."""

    pass


@dataclass
class ExecutionResult:
    """The result of a successful code execution.

    Attributes:
        text: Output text generated during execution.
        images: List of paths to images generated during execution.
    """

    text: str | None
    images: list[Path]


class Execution:
    """A code execution in an IPython kernel.

    Represents an ongoing or completed code execution. Created by
    [`KernelClient.submit`][ipybox.code_exec.client.KernelClient.submit].
    """

    def __init__(self, client: "KernelClient", req_id: str):
        """Initializes `Execution` object.

        Args:
            client: The client that initiated this code execution.
            req_id: Unique identifier of the code execution request.
        """
        self.client = client
        self.req_id = req_id

        self._chunks: list[str] = []
        self._images: list[Path] = []

        self._stream_consumed: bool = False

    async def result(self, timeout: float = 120) -> ExecutionResult:
        """Retrieves the complete result of this code execution.

        Waits until the result is available.

        Args:
            timeout: Maximum time in seconds to wait for the execution result.

        Raises:
            ExecutionError: If code execution raises an error.
            asyncio.TimeoutError: If code execution duration exceeds the timeout.
        """
        if not self._stream_consumed:
            async for _ in self.stream(timeout=timeout):
                pass

        return ExecutionResult(
            text="".join(self._chunks).strip() if self._chunks else None,
            images=self._images,
        )

    async def stream(self, timeout: float = 120) -> AsyncIterator[str]:
        """Streams the code execution output as it is generated.

        Once the stream is consumed, [`result`][ipybox.code_exec.client.Execution.result]
        returns immediately without waiting.

        Note:
            Generated images are not streamed. Their file paths can be obtained
            from the [`result`][ipybox.code_exec.client.Execution.result].

        Args:
            timeout: Maximum time in seconds to wait for execution to complete.

        Raises:
            ExecutionError: If code execution raises an error.
            asyncio.TimeoutError: If code execution duration exceeds the timeout.
        """
        try:
            async with asyncio.timeout(timeout):
                async for elem in self._stream():
                    match elem:
                        case str():
                            self._chunks.append(elem)
                            yield elem
                        case Path():
                            self._images.append(elem)
        except asyncio.TimeoutError:
            await self.client._interrupt_kernel()
            await asyncio.sleep(0.2)  # TODO: make configurable
            raise
        finally:
            self._stream_consumed = True

    async def _stream(self) -> AsyncIterator[str | Path]:
        saved_error = None
        while True:
            msg_dict = await self.client._read_message()
            msg_type = msg_dict["msg_type"]
            msg_id = msg_dict["parent_header"].get("msg_id", None)

            if msg_id != self.req_id:
                continue

            if msg_type == "stream":
                yield msg_dict["content"]["text"]
            elif msg_type == "error":
                saved_error = msg_dict
            elif msg_type == "execute_reply":
                if msg_dict["content"]["status"] == "error":
                    self._raise_error(saved_error or msg_dict)
                break
            elif msg_type in ["execute_result", "display_data"]:
                msg_data = msg_dict["content"]["data"]
                if "text/plain" in msg_data:
                    yield msg_data["text/plain"]
                if "image/png" in msg_data:
                    self.client.images_dir.mkdir(parents=True, exist_ok=True)

                    img_id = uuid4().hex[:8]
                    img_bytes = b64decode(msg_data["image/png"])
                    img_path = self.client.images_dir / f"{img_id}.png"

                    async with aiofiles.open(img_path, "wb") as f:
                        await f.write(img_bytes)

                    yield img_path

    def _raise_error(self, msg_dict):
        error_name = msg_dict["content"].get("ename", "Unknown Error")
        error_value = msg_dict["content"].get("evalue", "")
        error_trace = "\n".join(msg_dict["content"].get("traceback", []))
        raise ExecutionError(f"{error_name}: {error_value}\n{error_trace}")


class KernelClient:
    """Client for executing code in an IPython kernel.

    Connects to a [`KernelGateway`][ipybox.code_exec.server.KernelGateway] to
    create and communicate with an IPython kernel. Code execution is stateful:
    definitions and variables from previous executions are available to
    subsequent executions.

    Example:
        ```python
        async with KernelClient(host="localhost", port=8888) as client:
            result = await client.execute("x = 1 + 1")
            result = await client.execute("print(x)")  # prints 2
        ```
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 8888,
        images_dir: Path | None = None,
        heartbeat_interval: float = 10,
    ):
        """Initializes a kernel client configuration.

        Args:
            host: Hostname or IP address of the kernel gateway.
            port: Port number of the kernel gateway.
            images_dir: Directory for saving images generated during code
                execution. Defaults to `images` in the current directory.
            heartbeat_interval: Interval in seconds for WebSocket pings that
                keep the connection to the IPython kernel alive.
        """
        self.host = host
        self.port = port

        self.images_dir = images_dir or Path("images")

        self._heartbeat_interval = heartbeat_interval

        self._kernel_id = None
        self._session_id = uuid4().hex
        self._ws: WebSocketClientConnection | None = None

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()

    @property
    def kernel_id(self):
        """The ID of the running IPython kernel.

        Raises:
            RuntimeError: If not connected to a kernel.
        """
        if self._kernel_id is None:
            raise RuntimeError("Not connected to kernel")
        return self._kernel_id

    @property
    def base_http_url(self):
        return f"http://{self.host}:{self.port}/api/kernels"

    @property
    def kernel_http_url(self):
        return f"{self.base_http_url}/{self.kernel_id}"

    @property
    def kernel_ws_url(self):
        return f"ws://{self.host}:{self.port}/api/kernels/{self.kernel_id}/channels?session_id={self._session_id}"

    async def connect(self, retries: int = 10, retry_interval: float = 1.0):
        """Creates an IPython kernel and connects to it.

        Args:
            retries: Number of connection retries.
            retry_interval: Delay between connection retries in seconds.

        Raises:
            RuntimeError: If connection cannot be established after all retries.
        """
        for _ in range(retries):
            try:
                self._kernel_id = await self._create_kernel()
                break
            except Exception:
                await asyncio.sleep(retry_interval)
        else:
            raise RuntimeError("Failed to create kernel")

        self._ws = await websocket_connect(
            HTTPRequest(url=self.kernel_ws_url),
            ping_interval=self._heartbeat_interval,
            ping_timeout=self._heartbeat_interval,
        )
        logger.info(f"Connected to kernel (ping_interval={self._heartbeat_interval}s)")

        await self._init_kernel()

    async def disconnect(self):
        """Disconnects from and deletes the running IPython kernel."""
        if self._ws:
            self._ws.close()

        async with aiohttp.ClientSession() as session:
            async with session.delete(self.kernel_http_url):
                pass

    async def execute(self, code: str, timeout: float = 120) -> ExecutionResult:
        """Executes code in this client's IPython kernel and returns the result.

        Args:
            code: Python code to execute.
            timeout: Maximum time in seconds to wait for the execution result.

        Raises:
            ExecutionError: If code execution raises an error.
            asyncio.TimeoutError: If code execution duration exceeds the timeout.
        """
        execution = await self.submit(code)
        return await execution.result(timeout=timeout)

    async def submit(self, code: str) -> Execution:
        """Submits code for execution in this client's IPython kernel.

        Returns immediately with an [`Execution`][ipybox.code_exec.client.Execution]
        object for consuming the execution result.

        Args:
            code: Python code to execute.
        """
        req_id = uuid4().hex
        req = {
            "header": {
                "username": "",
                "version": "5.0",
                "session": self._session_id,
                "msg_id": req_id,
                "msg_type": "execute_request",
            },
            "parent_header": {},
            "channel": "shell",
            "content": {
                "code": code,
                "silent": False,
                "store_history": False,
                "user_expressions": {},
                "allow_stdin": False,
            },
            "metadata": {},
            "buffers": {},
        }

        await self._send_request(req)
        return Execution(client=self, req_id=req_id)

    async def _send_request(self, req):
        if self._ws is None:
            raise RuntimeError("Not connected to kernel")
        await self._ws.write_message(json_encode(req))

    async def _read_message(self) -> dict:
        if self._ws is None:
            raise RuntimeError("Not connected to kernel")
        msg = await self._ws.read_message()
        if msg is None:
            raise RuntimeError("Kernel disconnected")
        return json_decode(msg)

    async def _create_kernel(self):
        async with aiohttp.ClientSession() as session:
            async with session.post(url=self.base_http_url, json={"name": "python"}) as response:
                kernel = await response.json()
                return kernel["id"]

    async def _interrupt_kernel(self):
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.kernel_http_url}/interrupt", json={"kernel_id": self._kernel_id}
            ) as response:
                logger.info(f"Kernel interrupted: {response.status}")

    async def _init_kernel(self):
        await self.execute("%colors nocolor")
