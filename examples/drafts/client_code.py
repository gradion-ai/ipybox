import asyncio

from ipybox.tool_exec.server import ToolServer
from ipybox.utils import arun
from mcptools.fetch import fetch


def example() -> str:
    return fetch.run(fetch.Params(url="https://gradion.ai"))


async def main():
    async with ToolServer():
        result = await arun(example)
        print(result)


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    asyncio.run(main())
