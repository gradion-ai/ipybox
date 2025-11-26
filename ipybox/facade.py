import asyncio
from contextlib import AsyncExitStack, asynccontextmanager
from typing import AsyncIterator

from ipybox.kernel.executor import Execution, ExecutionClient, ExecutionError, ExecutionResult
from ipybox.kernel.gateway import KernelGateway
from ipybox.mcp.runner.approval import ApprovalClient, ApprovalRequest
from ipybox.mcp.runner.server import ToolServer


class CodeExecutionError(Exception):
    pass


class CodeExecution:
    def __init__(self, code: str):
        self._code = code
        self._queue = asyncio.Queue[ApprovalRequest | str | ExecutionResult | Exception]()
        self._result: ExecutionResult | None = None

    async def stream(self) -> AsyncIterator[ApprovalRequest | str]:
        if self._result is not None:
            return

        while True:
            item = await self._queue.get()
            match item:
                case ApprovalRequest():
                    yield item
                case str():
                    yield item
                case ExecutionError():
                    raise CodeExecutionError(item.args[0])
                case Exception():
                    raise item
                case ExecutionResult():
                    self._result = item
                    break
                case None:
                    break

    async def result(self) -> AsyncIterator[ApprovalRequest | ExecutionResult]:
        async for item in self.stream():
            match item:
                case ApprovalRequest():
                    yield item
                case str():
                    pass

        assert self._result is not None
        yield self._result


class CodeExecutor:
    def __init__(self):
        self._exec_client: ExecutionClient
        self._exit_stack = AsyncExitStack()

        self._work_queue: asyncio.Queue[CodeExecution | None] = asyncio.Queue()
        self._work_task: asyncio.Task[None]

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.stop()

    async def start(self):
        self._exec_client = await self._exit_stack.enter_async_context(self._executor())
        self._work_task = asyncio.create_task(self._work())

    async def stop(self):
        if self._work_task is not None:
            await self._work_queue.put(None)
            await self._work_task
        await self._exit_stack.aclose()

    @asynccontextmanager
    async def _executor(self) -> AsyncIterator[ExecutionClient]:
        async with KernelGateway():
            async with ToolServer(approval_required=True):
                async with ExecutionClient() as client:
                    yield client

    async def _complete(self, execution: Execution, queue: asyncio.Queue):
        try:
            async for chunk in execution.stream():
                await queue.put(chunk)
        except Exception as e:
            await queue.put(e)
        else:
            await queue.put(await execution.result())

    async def submit(self, code: str) -> CodeExecution:
        execution = CodeExecution(code)
        await self._work_queue.put(execution)
        return execution

    async def _work(self):
        while True:
            item = await self._work_queue.get()

            match item:
                case None:
                    break
                case CodeExecution():
                    async with ApprovalClient(callback=item._queue.put):
                        try:
                            execution = await self._exec_client.submit(item._code)
                        except Exception as e:
                            await item._queue.put(e)
                            continue
                        else:
                            complete = self._complete(execution, item._queue)
                            await asyncio.create_task(complete)
