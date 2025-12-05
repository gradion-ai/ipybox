import asyncio

from ipybox.code_exec import CodeExecutionChunk, CodeExecutionResult, CodeExecutor
from ipybox.tool_exec.approval.client import ApprovalRequest

CODE_1 = """
from time import sleep
from mcptools.test import tool_2

def foo():
    raise Exception("test")

print("Starting...")
#sleep(1)
result = tool_2.run(tool_2.Params(s="hello", delay=0))
#raise RuntimeError("test-2")
#foo()
print(result)
sleep(1)
print("Done")
"""


async def main():
    async with CodeExecutor() as executor:
        async for item in executor.stream(CODE_1, chunks=True):
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
