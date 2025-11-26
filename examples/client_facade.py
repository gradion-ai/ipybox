import asyncio

from ipybox.facade import Facade, FacadeExecution
from ipybox.mcp.runner.approval import Approval

CODE_1 = """
from time import sleep
from mcptools.test import tool_2

def foo():
    raise Exception("test")

print("Starting...")
#sleep(1)
result = tool_2.run(tool_2.Params(s="hello", delay=0))
#raise RuntimeError("test-2")
print(result)
sleep(1)
print("Done")
"""


async def consume_execution(execution: FacadeExecution):
    async for item in execution.stream():
        match item:
            case Approval():
                print(f"Approval request: {item}")
                await item.approve()
            case str():
                print(item)


async def main():
    async with Facade() as facade:
        execution_1 = await facade.submit(CODE_1)
        execution_2 = await facade.submit(CODE_1)
        await asyncio.gather(
            consume_execution(execution_1),
            consume_execution(execution_2),
        )


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    asyncio.run(main())
