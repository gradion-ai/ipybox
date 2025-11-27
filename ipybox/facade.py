import asyncio
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator

from ipybox.code_exec.client import Execution, ExecutionError, ExecutionResult, KernelClient
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


class CodeExecution:
    def __init__(self, code: str):
        self._code = code
        self._queue = asyncio.Queue[ApprovalRequest | str | ExecutionResult | Exception]()

        self._result: CodeExecutionResult | None = None
        self._error: Exception | None = None

    @property
    def code(self) -> str:
        return self._code

    def completed(self) -> bool:
        return self._result is not None or self._error is not None

    async def complete(
        self, stream: bool = False
    ) -> AsyncIterator[ApprovalRequest | CodeExecutionChunk | CodeExecutionResult]:
        if self.completed():
            return

        while True:
            item = await self._queue.get()
            match item:
                case ApprovalRequest():
                    yield item
                case str() if stream:
                    yield CodeExecutionChunk(text=item)
                case ExecutionError():
                    self._error = CodeExecutionError(item.args[0])
                    raise self._error
                case Exception():
                    self._error = item
                    raise self._error
                case ExecutionResult():
                    self._result = CodeExecutionResult(text=item.text, images=item.images)
                    yield self._result
                    break

    async def result(self) -> CodeExecutionResult:
        if self._error:
            raise self._error

        if self._result:
            return self._result

        async for item in self.complete(stream=False):
            match item:
                case ApprovalRequest():
                    await item.approve()

        assert self._error is None
        assert self._result is not None
        return self._result


class CodeExecutor:
    def __init__(
        self,
        tool_server_host: str = "localhost",
        tool_server_port: int | None = None,
        kernel_gateway_host: str = "localhost",
        kernel_gateway_port: int | None = None,
        sandbox: bool = False,
        sandbox_settings: Path | None = None,
        log_level: str = "INFO",
    ):
        self.tool_server_host = tool_server_host
        self.tool_server_port = tool_server_port or find_free_port()

        self.kernel_gateway_host = kernel_gateway_host
        self.kernel_gateway_port = kernel_gateway_port or find_free_port()

        self.sandbox = sandbox
        self.sandbox_settings = sandbox_settings
        self.log_level = log_level

        self._exit_stack = AsyncExitStack()
        self._client: KernelClient
        self._lock = asyncio.Lock()

        self._work_queue: asyncio.Queue[CodeExecution | None] = asyncio.Queue()
        self._work_task: asyncio.Task[None]

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.stop()

    async def start(self):
        self._client = await self._exit_stack.enter_async_context(self._executor())
        self._work_task = asyncio.create_task(self._work())

    async def stop(self):
        if self._work_task is not None:
            await self._work_queue.put(None)
            await self._work_task
        await self._exit_stack.aclose()

    async def reset(self):
        async with self._lock:
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

    async def submit(self, code: str) -> CodeExecution:
        execution = CodeExecution(code)
        await self._work_queue.put(execution)
        return execution

    @asynccontextmanager
    async def _executor(self) -> AsyncIterator[KernelClient]:
        async with ToolServer(
            host=self.tool_server_host,
            port=self.tool_server_port,
            log_level=self.log_level,
        ):
            async with KernelGateway(
                host=self.kernel_gateway_host,
                port=self.kernel_gateway_port,
                sandbox=self.sandbox,
                sandbox_settings=self.sandbox_settings,
                log_level=self.log_level,
                env={
                    "TOOL_SERVER_HOST": self.tool_server_host,
                    "TOOL_SERVER_PORT": str(self.tool_server_port),
                },
            ):
                async with KernelClient(
                    host=self.kernel_gateway_host,
                    port=self.kernel_gateway_port,
                ) as client:
                    yield client

    async def _complete(self, execution: Execution, queue: asyncio.Queue):
        try:
            async for chunk in execution.stream():
                await queue.put(chunk)
        except Exception as e:
            await queue.put(e)
        else:
            await queue.put(await execution.result())

    async def _work(self):
        while True:
            item = await self._work_queue.get()

            match item:
                case None:
                    break
                case CodeExecution(code=code):
                    async with ApprovalClient(
                        callback=item._queue.put,
                        host=self.tool_server_host,
                        port=self.tool_server_port,
                    ):
                        try:
                            execution = await self._client.submit(code)
                        except Exception as e:
                            await item._queue.put(e)
                            continue
                        else:
                            await self._complete(execution, item._queue)
