import asyncio

from ipybox.facade import Facade
from ipybox.mcp.runner.approval import Approval

CODE_1 = """
from time import sleep
from mcptools.test import tool_2

print("Starting...")
sleep(1)
result = tool_2.run(tool_2.Params(s="hello", delay=1))
print(result)
sleep(1)
print("Done")

"""


async def main():
    async with Facade() as facade:
        async for item in facade.execute(CODE_1):
            match item:
                case Approval():
                    print(f"Approval request ---: {item}")
                    await item.approve()
                case str():
                    print(item)

        async for item in facade.execute(CODE_1):
            match item:
                case Approval():
                    print(f"Approval request ---: {item}")
                    await item.approve()
                case str():
                    print(item)


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    asyncio.run(main())
