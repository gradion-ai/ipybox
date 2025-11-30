import asyncio
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator

from ipybox.code_exec.client import ExecutionError, ExecutionResult, KernelClient
from ipybox.code_exec.server import KernelGateway
from ipybox.tool_exec.approval.client import ApprovalClient, ApprovalRequest
from ipybox.tool_exec.client import reset
from ipybox.tool_exec.server import ToolServer
from ipybox.utils import find_free_port


class CodeExecutionError(Exception):
    pass


@dataclass
class CodeExecutionResult:
    text: str | None
    images: list[Path]


@dataclass
class CodeExecutionChunk:
    text: str


class CodeExecutor:
    def __init__(
        self,
        tool_server_host: str = "localhost",
        tool_server_port: int | None = None,
        kernel_gateway_host: str = "localhost",
        kernel_gateway_port: int | None = None,
        kernel_env: dict[str, str] | None = None,
        approval_timeout: float = 60,
        connect_timeout: float = 30,
        sandbox: bool = False,
        sandbox_config: Path | None = None,
        log_level: str = "INFO",
    ):
        self.tool_server_host = tool_server_host
        self.tool_server_port = tool_server_port or find_free_port()

        self.kernel_gateway_host = kernel_gateway_host
        self.kernel_gateway_port = kernel_gateway_port or find_free_port()
        self.kernel_env = kernel_env or {}

        self.approval_timeout = approval_timeout
        self.connect_timeout = connect_timeout

        self.sandbox = sandbox
        self.sandbox_config = sandbox_config
        self.log_level = log_level

        self._exit_stack = AsyncExitStack()
        self._client: KernelClient

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.stop()

    async def start(self):
        self._client = await self._exit_stack.enter_async_context(self._executor())

    async def stop(self):
        await self._exit_stack.aclose()

    async def reset(self):
        await reset(
            host=self.tool_server_host,
            port=self.tool_server_port,
        )
        await self._client.disconnect()
        self._client = KernelClient(
            host=self.kernel_gateway_host,
            port=self.kernel_gateway_port,
        )
        await self._client.connect()

    async def execute(
        self, code: str, timeout: float = 120, stream: bool = False
    ) -> AsyncIterator[ApprovalRequest | CodeExecutionChunk | CodeExecutionResult]:
        queue: asyncio.Queue[ApprovalRequest | str | ExecutionResult | Exception] = asyncio.Queue()

        async def stream_execution():
            try:
                async for item in self._client.stream(code, timeout=timeout):
                    await queue.put(item)
            except Exception as e:
                await queue.put(e)

        async with ApprovalClient(
            callback=queue.put,
            host=self.tool_server_host,
            port=self.tool_server_port,
        ):
            task = asyncio.create_task(stream_execution())
            try:
                while True:
                    item = await queue.get()
                    match item:
                        case ApprovalRequest():
                            yield item
                        case str() if stream:
                            yield CodeExecutionChunk(text=item)
                        case ExecutionError():
                            raise CodeExecutionError(item.args[0])
                        case Exception():
                            raise item
                        case ExecutionResult():
                            yield CodeExecutionResult(text=item.text, images=item.images)
                            break
            finally:
                await task

    @asynccontextmanager
    async def _executor(self) -> AsyncIterator[KernelClient]:
        async with ToolServer(
            host=self.tool_server_host,
            port=self.tool_server_port,
            approval_required=True,
            approval_timeout=self.approval_timeout,
            connect_timeout=self.connect_timeout,
            log_level=self.log_level,
        ):
            async with KernelGateway(
                host=self.kernel_gateway_host,
                port=self.kernel_gateway_port,
                sandbox=self.sandbox,
                sandbox_config=self.sandbox_config,
                log_level=self.log_level,
                env=self.kernel_env
                | {
                    "TOOL_SERVER_HOST": self.tool_server_host,
                    "TOOL_SERVER_PORT": str(self.tool_server_port),
                },
            ):
                async with KernelClient(
                    host=self.kernel_gateway_host,
                    port=self.kernel_gateway_port,
                ) as client:
                    yield client
