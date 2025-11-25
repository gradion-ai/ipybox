import asyncio

from ipybox.mcp.client import MCPClient


async def main():
    async with MCPClient(
        server_params={
            "command": "python",
            "args": ["-m", "ipybox.mcp.server"],
        },
    ) as client:
        result = await client.run("install_package", {"package_name": "yfinance"})
        result = await client.run(
            "execute_ipython_cell", {"code": "import yfinance as yf\nprint(yf.Ticker('AAPL').info)"}
        )
        print(result)


if __name__ == "__main__":
    asyncio.run(main())
