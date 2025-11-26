import asyncio
from contextlib import AsyncExitStack, asynccontextmanager
from typing import AsyncIterator

from ipybox.kernel.executor import Execution, ExecutionClient
from ipybox.kernel.gateway import KernelGateway
from ipybox.mcp.runner.approval import Approval, ApprovalClient
from ipybox.mcp.runner.server import ToolServer


class Facade:
    def __init__(self):
        self._queue: asyncio.Queue[str | Approval | None] = asyncio.Queue()
        self._executor: ExecutionClient | None = None
        self._exit_stack = AsyncExitStack()

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.stop()

    async def on_approval(self, approval: Approval):
        await self._queue.put(approval)

    @asynccontextmanager
    async def _execution_client(self):
        async with KernelGateway():
            async with ToolServer(approval_required=True):
                async with ApprovalClient(callback=self.on_approval):
                    async with ExecutionClient() as client:
                        self._executor = client
                        yield

    async def _complete_execution(self, execution: Execution):
        async for chunk in execution.stream():
            await self._queue.put(chunk)
        await self._queue.put(None)

    async def execute(self, code: str) -> AsyncIterator[Approval | str]:
        if not self._executor:
            raise RuntimeError("Facade not started")

        execution = await self._executor.submit(code)

        task = asyncio.create_task(self._complete_execution(execution))

        while True:
            item = await self._queue.get()
            if item is None:
                break
            yield item

        await task

    async def start(self):
        self._session = await self._exit_stack.enter_async_context(self._execution_client())

    async def stop(self):
        try:
            await self._exit_stack.aclose()
        except RuntimeError:
            pass
        finally:
            self._session = None
