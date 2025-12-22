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


class KernelClient:
    """Client for executing code in an IPython kernel.

    Connects to a [`KernelGateway`][ipybox.kernel_mgr.server.KernelGateway] to
    create and communicate with an IPython kernel. Code execution is stateful:
    definitions and variables from previous executions are available to
    subsequent executions.

    Example:
        ```python
        async with KernelClient(host="localhost", port=8888) as client:
            # Simple execution
            result = await client.execute("print('hello')")
            print(result.text)

            # Streaming execution
            async for item in client.stream("print('hello')"):
                match item:
                    case str():
                        print(f"Chunk: {item}")
                    case ExecutionResult():
                        print(f"Result: {item}")
        ```
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 8888,
        images_dir: Path | None = None,
        ping_interval: float = 10,
    ):
        """
        Args:
            host: Hostname or IP address of the kernel gateway.
            port: Port number of the kernel gateway.
            images_dir: Directory for saving images generated during code
                execution. Defaults to `images` in the current directory.
            ping_interval: Interval in seconds for WebSocket pings that
                keep the connection to the IPython kernel alive.
        """
        self.host = host
        self.port = port

        self.images_dir = images_dir or Path("images")
        self.ping_interval = ping_interval

        self._kernel_id: str | None = None
        self._session_id: str | None = None
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
                self._session_id = uuid4().hex
                break
            except Exception:
                await asyncio.sleep(retry_interval)
        else:
            raise RuntimeError("Failed to create kernel")

        self._ws = await websocket_connect(
            HTTPRequest(url=self.kernel_ws_url),
            ping_interval=self.ping_interval,
            ping_timeout=self.ping_interval * 0.9,
        )
        logger.info(f"Connected to kernel (ping_interval={self.ping_interval}s)")

        # TODO: further investigate why this is needed on linux
        # If not present, non-deterministically causes a read
        # timeout during _init_kernel
        await asyncio.sleep(0.2)

        await self._init_kernel()

    async def disconnect(self):
        """Disconnects from and deletes the running IPython kernel."""
        if self._ws:
            self._ws.close()
            self._ws = None

        if self._kernel_id:
            async with aiohttp.ClientSession() as session:
                async with session.delete(self.kernel_http_url):
                    pass
            self._kernel_id = None
            self._session_id = None

    async def reset(self):
        """Resets the IPython kernel to a clean state.

        Deletes the running kernel and creates a new one.
        """
        await self.disconnect()
        await self.connect()

    async def execute(self, code: str, timeout: float | None = None) -> ExecutionResult:  # type: ignore
        """Executes code in this client's IPython kernel and returns the result.

        Waits for execution to complete and returns the final result.
        Use [`stream`][ipybox.kernel_mgr.client.KernelClient.stream] for
        incremental output.

        Args:
            code: Python code to execute.
            timeout: Maximum time in seconds to wait for the execution result.
                If `None`, no timeout is applied.

        Returns:
            The execution result containing output text and generated images.

        Raises:
            ExecutionError: If code execution raises an error.
            asyncio.TimeoutError: If code execution duration exceeds the timeout.
        """
        async for item in self.stream(code, timeout):
            match item:
                case str():
                    pass
                case ExecutionResult():
                    return item

    async def stream(self, code: str, timeout: float | None = None) -> AsyncIterator[str | ExecutionResult]:
        """Executes code in this client's IPython kernel.

        Yields output chunks as strings during execution, and yields the
        final ExecutionResult as the last item.

        Args:
            code: Python code to execute.
            timeout: Maximum time in seconds to wait for the execution result.
                If `None`, no timeout is applied.

        Yields:
            str: Output text chunks generated during execution.
            ExecutionResult: The final result containing complete text and images.

        Raises:
            ExecutionError: If code execution raises an error.
            asyncio.TimeoutError: If code execution duration exceeds the timeout.
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

        chunks: list[str] = []
        images: list[Path] = []
        saved_error = None

        try:
            async with asyncio.timeout(timeout):
                while True:
                    msg_dict = await self._read_message()
                    msg_type = msg_dict["msg_type"]
                    msg_id = msg_dict["parent_header"].get("msg_id", None)

                    if msg_id != req_id:
                        continue

                    if msg_type == "stream":
                        text = msg_dict["content"]["text"]
                        chunks.append(text)
                        yield text
                    elif msg_type == "error":
                        saved_error = msg_dict
                    elif msg_type == "execute_reply":
                        if msg_dict["content"]["status"] == "error":
                            self._raise_error(saved_error or msg_dict)
                        break
                    elif msg_type in ["execute_result", "display_data"]:
                        msg_data = msg_dict["content"]["data"]
                        if "text/plain" in msg_data:
                            text = msg_data["text/plain"]
                            chunks.append(text)
                            yield text
                        if "image/png" in msg_data:
                            self.images_dir.mkdir(parents=True, exist_ok=True)
                            img_id = uuid4().hex[:8]
                            img_bytes = b64decode(msg_data["image/png"])
                            img_path = self.images_dir / f"{img_id}.png"
                            async with aiofiles.open(img_path, "wb") as f:
                                await f.write(img_bytes)
                            images.append(img_path)
        except asyncio.TimeoutError:
            await self._interrupt_kernel()
            await asyncio.sleep(0.2)
            raise

        yield ExecutionResult(
            text="".join(chunks).strip() if chunks else None,
            images=images,
        )

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
        await self.execute("%colors nocolor", timeout=10)

    def _raise_error(self, msg_dict):
        error_name = msg_dict["content"].get("ename", "Unknown Error")
        error_value = msg_dict["content"].get("evalue", "")
        error_trace = "\n".join(msg_dict["content"].get("traceback", []))
        raise ExecutionError(f"{error_name}: {error_value}\n{error_trace}")
