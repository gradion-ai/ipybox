import asyncio

from ipybox.code_exec import CodeExecutionResult, CodeExecutor
from ipybox.tool_exec.approval.client import ApprovalRequest

CODE = """
from mcptools.fetch import fetch

result = fetch.run(fetch.Params(url="https://example.com"))
print(result)
"""


async def main():
    async with CodeExecutor() as executor:
        async for item in executor.stream(CODE):
            match item:
                case ApprovalRequest():
                    await item.accept()
                case CodeExecutionResult():
                    print(item.text)


if __name__ == "__main__":
    asyncio.run(main())
