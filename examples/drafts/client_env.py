import asyncio

from ipybox.code_exec import CodeExecutionChunk, CodeExecutionResult, CodeExecutor
from ipybox.tool_exec.approval.client import ApprovalRequest

CODE_1 = """
import os
print(os.environ["TEST_VAR"])
"""


async def main():
    async with CodeExecutor(kernel_env={"TEST_VAR": "test_val"}) as executor:
        async for item in executor.execute(CODE_1, stream=True):
            match item:
                case ApprovalRequest():
                    print(f"Approval request: {item}")
                    await item.accept()
                case CodeExecutionChunk():
                    print(item)
                case CodeExecutionResult():
                    print(item)


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    asyncio.run(main())
