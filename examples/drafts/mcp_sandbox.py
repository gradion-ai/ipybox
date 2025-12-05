import asyncio
from pathlib import Path

from ipybox import ApprovalRequest, CodeExecutionResult, CodeExecutor, generate_mcp_sources

CODE = """
from mcptools.filesystem import list_directory as ld
from mcptools.filesystem import read_file as rf

result = ld.run(ld.Params(path="/Users/martin/Development/gradion/ipybox"))
print(result.content)

try:
    result = rf.run(rf.Params(path="/Users/martin/Development/gradion/ipybox/.env"))
    print(result.content)
except Exception as e:
    print("Read access to .env denied")
else:
    raise RuntimeError("Read access to .env granted")
"""


server_params = {
    "command": "srt",
    "args": [
        "--settings",
        "examples/drafts/mcp_sandbox.json",
        "npx",
        "-y",
        "@modelcontextprotocol/server-filesystem",
        ".",
    ],
}


async def main():
    await generate_mcp_sources("filesystem", server_params, Path("mcptools"))

    async with CodeExecutor(sandbox=True) as executor:
        async for item in executor.stream(CODE):
            match item:
                case ApprovalRequest():
                    await item.accept()
                case CodeExecutionResult():
                    print(item.text)


if __name__ == "__main__":
    asyncio.run(main())
