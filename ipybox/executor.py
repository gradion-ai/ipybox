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
    """Exception raised when connection to an IPython kernel fails."""

    pass


class ExecutionError(Exception):
    """Exception raised when code execution in the IPython kernel fails.

    Args:
        message: Error message
        trace: Stack trace string representation
    """

    def __init__(self, message: str, trace: str | None = None):
        super().__init__(message)
        self.trace = trace


@dataclass
class ExecutionResult:
    """The result of a code execution.

    Args:
        text: Output text generated during execution
        images: List of images generated during execution
    """

    text: str | None
    images: list[Image.Image]


class Execution:
    """A code execution in an IPython kernel.

    Args:
        client: The client instance that created this execution
        req_id: Unique identifier for the execution request
    """

    def __init__(self, client: "ExecutionClient", req_id: str):
        self.client = client
        self.req_id = req_id

        self._chunks: list[str] = []
        self._images: list[Image.Image] = []

        self._stream_consumed: bool = False

    async def result(self, timeout: float = 120) -> ExecutionResult:
        """Waits for execution to complete and returns the final result.

        If a timeout is reached, the kernel is interrupted.

        Args:
            timeout: Maximum time to wait in seconds. Defaults to 120.

        Returns:
            ExecutionResult object

        Raises:
            asyncio.TimeoutError: If execution exceeds timeout duration
        """
        if not self._stream_consumed:
            async for _ in self.stream(timeout=timeout):
                pass

        return ExecutionResult(
            text="".join(self._chunks).strip() if self._chunks else None,
            images=self._images,
        )

    async def stream(self, timeout: float = 120) -> AsyncIterator[str]:
        """Streams the execution output text as it becomes available.

        Args:
            timeout: Maximum time to wait in seconds. Defaults to 120.

        Yields:
            Output text chunks as they arrive

        Raises:
            asyncio.TimeoutError: If execution exceeds timeout duration
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
        while True:
            msg_dict = await self.client._read_message()
            msg_type = msg_dict["msg_type"]
            msg_id = msg_dict["parent_header"].get("msg_id", None)

            if msg_id != self.req_id:
                continue

            if msg_type == "stream":
                yield msg_dict["content"]["text"]
            elif msg_type == "error":
                self._raise_error(msg_dict)
            elif msg_type == "execute_reply":
                if msg_dict["content"]["status"] == "error":
                    self._raise_error(msg_dict)
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
    """A context manager for executing code in an IPython kernel.

    Args:
        host: Hostname where the code execution container is running
        port: Host port for the container's executor port
        heartbeat_interval: Interval in seconds between heartbeat pings. Defaults to 10.

    Example:
        ```python
        from ipybox import ExecutionClient, ExecutionContainer

        binds = {"/host/path": "example/path"}
        env = {"API_KEY": "secret"}

        async with ExecutionContainer(binds=binds, env=env) as container:
            async with ExecutionClient(host="localhost", port=container.executor_port) as client:
                result = await client.execute("print('Hello, world!')")
                print(result.text)
        ```
        > Hello, world!
    """

    def __init__(self, port: int, host: str = "localhost", heartbeat_interval: float = 10):
        self.port = port
        self.host = host

        self._heartbeat_interval = heartbeat_interval
        self._heartbeat_callback = None

        self._kernel_id = None
        self._ws: WebSocketClientConnection

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
        """Creates and connects to an IPython kernel.

        Args:
            retries: Number of connection attempts. Defaults to 10.
            retry_interval: Delay between retries in seconds. Defaults to 1.0.

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

        self.heartbeat_callback = PeriodicCallback(self._ping_kernel, self._heartbeat_interval * 1000)
        self.heartbeat_callback.start()
        logger.info(f"Started heartbeat (interval = {self._heartbeat_interval}s)")

        await self._init_kernel()

    async def disconnect(self):
        """Closes the connection to the kernel and cleans up resources."""
        self.heartbeat_callback.stop()
        self._ws.close()
        async with aiohttp.ClientSession() as session:
            async with session.delete(self.kernel_http_url):
                pass

    async def execute(self, code: str, timeout: float = 120) -> ExecutionResult:
        """Executes code and returns the result.

        Args:
            code: Code to execute
            timeout: Maximum execution time in seconds. Defaults to 120.

        Returns:
            ExecutionResult object

        Raises:
            ExecutionError: If code execution raised an error
            asyncio.TimeoutError: If execution exceeds timeout duration
        """
        execution = await self.submit(code)
        return await execution.result(timeout=timeout)

    async def submit(self, code: str) -> Execution:
        """Submits code for execution and returns an Execution object to track it.

        Args:
            code: Python code to execute

        Returns:
            An Execution object to track the code execution
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
        await self._ws.write_message(json_encode(req))

    async def _read_message(self) -> dict:
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
            self._ws.ping()
        except tornado.iostream.StreamClosedError as e:
            logger.error("Kernel disconnected", e)

    async def _init_kernel(self):
        await self.execute("""
            import sys

            sys.path.append("/app")
            """)
