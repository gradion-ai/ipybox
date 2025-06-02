import argparse
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from mcp.server.fastmcp import FastMCP

STDIO_SERVER_PATH = Path(__file__)
HTTP_SERVER_PORT = 8710
SSE_SERVER_PORT = 8711


async def tool_1(s: str) -> str:
    """
    This is tool 1.

    Args:
        s: A string
    """
    return f"You passed to tool 1: {s}"


async def tool_2(s: str) -> str:
    """
    This is tool 2.
    """
    return f"You passed to tool 2: {s}"


def create_server(**kwargs) -> FastMCP:
    server = FastMCP("Test MCP Server", **kwargs)
    server.add_tool(tool_1, name="tool-1")
    server.add_tool(tool_2)
    return server


@asynccontextmanager
async def streamable_http_server(
    host: str = "0.0.0.0",
    port: int = 8710,
    json_response: bool = True,
) -> AsyncIterator[FastMCP]:
    server = create_server(host=host, port=port, json_response=json_response)
    async with _server(server.streamable_http_app(), server.settings):
        yield server


@asynccontextmanager
async def sse_server(
    host: str = "0.0.0.0",
    port: int = 8711,
) -> AsyncIterator[FastMCP]:
    server = create_server(host=host, port=port)
    async with _server(server.sse_app(), server.settings):
        yield server


@asynccontextmanager
async def _server(app, settings):
    import uvicorn

    cfg = uvicorn.Config(
        app,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )
    server = uvicorn.Server(cfg)
    task = asyncio.create_task(server.serve())
    while not server.started:
        await asyncio.sleep(0.01)

    yield

    server.should_exit = True
    await task


def main():
    parser = argparse.ArgumentParser(description="Test MCP Server with configurable transport")
    parser.add_argument(
        "--transport",
        "-t",
        choices=["stdio", "streamable-http", "sse"],
        default="stdio",
        help="Transport type to use (default: stdio)",
    )
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)")
    parser.add_argument("--port", "-p", type=int, default=8000, help="Port to bind to (default: 8000)")

    args = parser.parse_args()

    server = create_server(host=args.host, port=args.port)
    server.run(transport=args.transport)


if __name__ == "__main__":
    main()
