import asyncio

from ipybox.mcp_tools.runner.server import ToolServer
from ipybox.utils import arun
from mcptools.brave_search import brave_web_search as bws


def example() -> str:
    return bws.run(bws.Params(query="martin krasser", count=3))


async def main():
    async with ToolServer():
        result = await arun(example)
        print(result)


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    asyncio.run(main())
