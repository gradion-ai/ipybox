import asyncio

from ipybox.code_exec import CodeExecution, CodeExecutor
from ipybox.mcp_tools.approval.client import ApprovalRequest

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


async def consume_execution(execution: CodeExecution):
    async for item in execution.stream():
        match item:
            case ApprovalRequest():
                print(f"Approval request: {item}")
                await item.approve()
            case str():
                print(item)


async def main():
    async with CodeExecutor() as facade:
        execution_1 = await facade.submit(CODE_1)
        # execution_2 = await facade.submit(CODE_1)
        await asyncio.gather(
            consume_execution(execution_1),
            # consume_execution(execution_2),
        )


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    asyncio.run(main())
