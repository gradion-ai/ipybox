import asyncio
import io
import logging
from base64 import b64decode
from dataclasses import dataclass
from typing import AsyncIterator
from uuid import uuid4

import aiohttp
import tornado
from PIL import Image
from tornado.escape import json_decode, json_encode
from tornado.httpclient import HTTPRequest
from tornado.ioloop import PeriodicCallback
from tornado.websocket import WebSocketClientConnection, websocket_connect

logger = logging.getLogger(__name__)


class ConnectionError(Exception):
    """Raised when a connection to an IPython kernel cannot be established."""


class ExecutionError(Exception):
    """Raised when code execution in an IPython kernel raises an error.

    Args:
        message: Error message
        trace: String representation of the stack trace.
    """

    def __init__(self, message: str, trace: str | None = None):
        super().__init__(message)
        self.trace = trace


@dataclass
class ExecutionResult:
    """The result of a successful code execution.

    Args:
        text: Output text generated during execution
        images: List of images generated during execution
    """

    text: str | None
    images: list[Image.Image]


class Execution:
    """A code execution in an IPython kernel.

    Args:
        client: The client that initiated this code execution
        req_id: Unique identifier of the code execution request
    """

    def __init__(self, client: "ExecutionClient", req_id: str):
        self.client = client
        self.req_id = req_id

        self._chunks: list[str] = []
        self._images: list[Image.Image] = []

        self._stream_consumed: bool = False

    async def result(self, timeout: float = 120) -> ExecutionResult:
        """Retrieves the complete result of this code execution. Waits until the
        result is available.

        Args:
            timeout: Maximum time in seconds to wait for the execution result

        Raises:
            ExecutionError: If code execution raises an error
            asyncio.TimeoutError: If code execution duration exceeds the specified timeout
        """
        if not self._stream_consumed:
            async for _ in self.stream(timeout=timeout):
                pass

        return ExecutionResult(
            text="".join(self._chunks).strip() if self._chunks else None,
            images=self._images,
        )

    async def stream(self, timeout: float = 120) -> AsyncIterator[str]:
        """Streams the code execution result as it is generated. Once the stream
        is consumed, a [`result`][ipybox.executor.Execution.result] is immediately
        available without waiting.

        Generated images are not streamed. They can be obtained from the
        return value of [`result`][ipybox.executor.Execution.result].

        Args:
            timeout: Maximum time in seconds to wait for the complete execution result

        Raises:
            ExecutionError: If code execution raises an error
            asyncio.TimeoutError: If code execution duration exceeds the specified timeout
        """
        try:
            async with asyncio.timeout(timeout):
                async for elem in self._stream():
                    match elem:
                        case str():
                            self._chunks.append(elem)
                            yield elem
                        case Image.Image():
                            self._images.append(elem)
        except asyncio.TimeoutError:
            await self.client._interrupt_kernel()
            await asyncio.sleep(0.2)  # TODO: make configurable
            raise
        finally:
            self._stream_consumed = True

    async def _stream(self) -> AsyncIterator[str | Image.Image]:
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
                yield msg_data["text/plain"]
                if "image/png" in msg_data:
                    image_bytes_io = io.BytesIO(b64decode(msg_data["image/png"]))
                    image = Image.open(image_bytes_io)
                    image.load()
                    yield image

    def _raise_error(self, msg_dict):
        error_name = msg_dict["content"].get("ename", "Unknown Error")
        error_value = msg_dict["content"].get("evalue", "")
        error_trace = "\n".join(msg_dict["content"]["traceback"])
        raise ExecutionError(f"{error_name}: {error_value}", error_trace)


class ExecutionClient:
    """
    Context manager for executing code in an IPython kernel running in an
    [`ExecutionContainer`][ipybox.container.ExecutionContainer].
    The kernel is created on entering the context and destroyed on exit.
    The container's `/app` directory is added to the kernel's Python path.

    Code execution is stateful for a given `ExecutionClient` instance. Definitions and
    variables of previous executions are available to subsequent executions.

    Args:
        port: Host port for the container's executor port
        host: Hostname or IP address of the container's host
        heartbeat_interval: Ping interval for keeping the websocket connection to
            the IPython kernel alive.
    """

    def __init__(self, port: int, host: str = "localhost", heartbeat_interval: float = 10):
        self.port = port
        self.host = host

        self._heartbeat_interval = heartbeat_interval
        self._heartbeat_callback: PeriodicCallback | None = None

        self._kernel_id = None
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
            ValueError: If not connected to a kernel
        """
        if self._kernel_id is None:
            raise ValueError("Not connected to kernel")
        return self._kernel_id

    @property
    def base_http_url(self):
        return f"http://{self.host}:{self.port}/api/kernels"

    @property
    def kernel_http_url(self):
        return f"{self.base_http_url}/{self.kernel_id}"

    @property
    def kernel_ws_url(self):
        return f"ws://{self.host}:{self.port}/api/kernels/{self.kernel_id}/channels"

    async def connect(self, retries: int = 10, retry_interval: float = 1.0):
        """Creates an IPython kernel and connects to it.

        Args:
            retries: Number of connection retries.
            retry_interval: Delay between connection retries in seconds.

        Raises:
            ConnectionError: If connection cannot be established after all retries
        """
        for _ in range(retries):
            try:
                self._kernel_id = await self._create_kernel()
                break
            except Exception:
                await asyncio.sleep(retry_interval)
        else:
            raise ConnectionError("Failed to create kernel")

        self._ws = await websocket_connect(HTTPRequest(url=self.kernel_ws_url))
        logger.info("Connected to kernel")

        self._heartbeat_callback = PeriodicCallback(self._ping_kernel, self._heartbeat_interval * 1000)
        self._heartbeat_callback.start()
        logger.info(f"Started heartbeat (interval = {self._heartbeat_interval}s)")

        await self._init_kernel()

    async def disconnect(self):
        """Disconnects from and deletes the running IPython kernel."""
        if self._heartbeat_callback:
            self._heartbeat_callback.stop()

        if self._ws:
            self._ws.close()

        async with aiohttp.ClientSession() as session:
            async with session.delete(self.kernel_http_url):
                pass

    async def execute(self, code: str, timeout: float = 120) -> ExecutionResult:
        """Executes code in this client's IPython kernel and returns the result.

        Args:
            code: Code to execute
            timeout: Maximum time in seconds to wait for the execution result

        Raises:
            ExecutionError: If code execution raises an error
            asyncio.TimeoutError: If code execution duration exceeds the specified timeout
        """
        execution = await self.submit(code)
        return await execution.result(timeout=timeout)

    async def submit(self, code: str) -> Execution:
        """Submits code for execution in this client's IPython kernel and returns an
        [`Execution`][ipybox.executor.Execution] object for consuming the execution result.

        Args:
            code: Python code to execute

        Returns:
            A [`Execution`][ipybox.executor.Execution] object to track the code execution.
        """
        req_id = uuid4().hex
        req = {
            "header": {
                "username": "",
                "version": "5.0",
                "session": "",
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
            raise ConnectionError("Not connected to kernel")
        await self._ws.write_message(json_encode(req))

    async def _read_message(self) -> dict:
        if self._ws is None:
            raise ConnectionError("Not connected to kernel")
        return json_decode(await self._ws.read_message())

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

    async def _ping_kernel(self):
        try:
            self._ws.ping()  # type: ignore
        except tornado.iostream.StreamClosedError as e:
            logger.error("Kernel disconnected", e)

    async def _init_kernel(self):
        await self.execute("""
            import sys

            sys.path.append("/app")
            """)
