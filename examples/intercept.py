import asyncio

from ipybox import ApprovalRequest, CodeExecutionChunk, CodeExecutionResult, CodeExecutor


async def intercept():
    """Intercept shell commands with a custom handler."""
    handler = """\
print(f"[intercepted] {cmd}")
return _run(cmd)
"""

    code = """\
for i in range(3):
    !echo {i}
result = !echo captured
print(f"result = {result}")
"""

    async with CodeExecutor(shell_cmd_handler=handler) as executor:
        async for item in executor.stream(code, chunks=True):
            match item:
                case CodeExecutionChunk():
                    print(item.text, end="")
                case CodeExecutionResult():
                    pass


async def approve():
    """Require approval for shell commands."""
    code = """\
for i in range(3):
    !echo {i}
result = !echo captured {i}
print(f"result = {result}")
"""

    async with CodeExecutor(approve_shell_cmds=True) as executor:
        async for item in executor.stream(code, chunks=True):
            match item:
                case ApprovalRequest():
                    print(f"[approve] {item.tool_name}: {item.tool_args}")
                    await item.accept()
                case CodeExecutionChunk():
                    print(item.text, end="")
                case CodeExecutionResult():
                    pass


async def main():
    # print("--- intercept ---")
    # await intercept()
    # print()
    print("--- approve ---")
    await approve()


if __name__ == "__main__":
    asyncio.run(main())
