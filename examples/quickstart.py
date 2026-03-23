import asyncio
from pathlib import Path

from ipybox import ApprovalRequest, CodeExecutionResult, CodeExecutor, generate_mcp_sources

SERVER_PARAMS = {
    "command": "npx",
    "args": [
        "-y",
        "@brave/brave-search-mcp-server",
        "--transport",
        "stdio",
    ],
    "env": {
        "BRAVE_API_KEY": "${BRAVE_API_KEY}",
    },
}

# --8<-- [start:tool_call_code]
CODE = """
from mcptools.brave_search.brave_image_search import Params, Result, run

result: Result = run(Params(query="neural topic models", count=3))

for image in result.items:
    print(f"- [{image.title}]({image.properties.url})")
"""
# --8<-- [end:tool_call_code]


async def basic():
    # --8<-- [start:basic_execution]
    async with CodeExecutor() as executor:
        # Execute Python code
        result = await executor.execute("print('hello from Python')")
        print(result.text)

        # Execute a shell command
        result = await executor.execute("!echo hello from shell")
        print(result.text)

        # Mix Python and shell in one block
        code = """
        name = "ipybox"
        !echo hello from {name}

        # Capture shell output into a Python variable
        files = !ls /tmp
        print(f"found {len(files)} entries in /tmp")
        """
        result = await executor.execute(code)
        print(result.text)
    # --8<-- [end:basic_execution]


async def tool_calling():
    await generate_mcp_sources(
        server_name="brave_search",
        server_params=SERVER_PARAMS,
        root_dir=Path("mcptools"),
    )

    # --8<-- [start:tool_call_execute]
    async with CodeExecutor() as executor:
        result = await executor.execute(CODE)
        print(result.text)
    # --8<-- [end:tool_call_execute]


async def approval():
    await generate_mcp_sources(
        server_name="brave_search",
        server_params=SERVER_PARAMS,
        root_dir=Path("mcptools"),
    )

    # --8<-- [start:approval_code]
    SEARCH_AND_ECHO = """
    from mcptools.brave_search.brave_image_search import Params, Result, run

    result: Result = run(Params(query="neural topic models", count=3))
    !echo "Found {len(result.items)} images"
    """
    # --8<-- [end:approval_code]

    # --8<-- [start:approval]
    async with CodeExecutor(
        approve_tool_calls=True,  # default
        approve_shell_cmds=True,
    ) as executor:
        async for item in executor.stream(SEARCH_AND_ECHO):
            match item:
                case ApprovalRequest(tool_name="shell" | "shell_magic", tool_args=args):
                    print(f"Shell: {args['cmd']}")
                    await item.accept()
                case ApprovalRequest(tool_name=name, tool_args=args):
                    print(f"Tool call: {name}({args})")
                    await item.accept()
                case CodeExecutionResult(text=text):
                    print(text)
    # --8<-- [end:approval]


async def main():
    await basic()
    await tool_calling()
    await approval()


if __name__ == "__main__":
    asyncio.run(main())
