import asyncio

from ipybox.facade import CodeExecution, CodeExecutionChunk, CodeExecutionResult, CodeExecutor
from ipybox.tool_exec.approval.client import ApprovalRequest

CODE_1 = """
import os
print(os.environ["TEST_VAR"])
"""


async def consume_execution(execution: CodeExecution):
    async for item in execution.complete(stream=True):
        match item:
            case ApprovalRequest():
                print(f"Approval request: {item}")
                await item.approve()
            case CodeExecutionChunk():
                print(item)
            case CodeExecutionResult():
                print(item)


async def main():
    async with CodeExecutor(kernel_env={"TEST_VAR": "test_val"}) as facade:
        execution = await facade.submit(CODE_1)
        await consume_execution(execution)


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    asyncio.run(main())
