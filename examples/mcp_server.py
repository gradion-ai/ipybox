import argparse
import asyncio
import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.WARNING)

STDIO_SERVER_PATH = Path(__file__)
HTTP_SERVER_PORT = 8710
SSE_SERVER_PORT = 8711


class InnerResult(BaseModel):
    """Inner nested result structure."""

    code: int = Field(description="Status code")
    details: str = Field(description="Detailed information")


class OuterResult(BaseModel):
    """Outer result structure containing nested data."""

    status: str = Field(description="Overall status of the operation")
    inner: InnerResult = Field(description="Nested result data")
    count: int = Field(description="Number of items processed")


async def tool_1(s: str) -> str:
    """
    This is tool 1.

    Args:
        s: A string
    """
    if s == "error":
        raise ValueError("This is a test error")
    return f"You passed to tool 1: {s}"


async def tool_2(s: str, delay: float = 2) -> str:
    """
    This is tool 2.
    """

    await asyncio.sleep(delay)
    return f"You passed to tool 2: {s}"


async def tool_3(name: str, level: int) -> OuterResult:
    """
    This is tool 3 with nested structured output.

    Args:
        name: A name to process
        level: Processing level
    """
    return OuterResult(
        status=f"completed_{name}",
        inner=InnerResult(
            code=level * 100,
            details=f"Processing {name} at level {level}",
        ),
        count=len(name),
    )


@asynccontextmanager
async def server_lifespan(server: FastMCP):
    yield
    print("Server is being closed/terminated", file=sys.stderr)


def create_server(**kwargs) -> FastMCP:
    if "lifespan" not in kwargs:
        kwargs["lifespan"] = server_lifespan

    server = FastMCP("Test MCP Server", **kwargs)
    server.add_tool(tool_1, structured_output=False, name="tool-1")
    server.add_tool(tool_2, structured_output=False)
    server.add_tool(tool_3)
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
    try:
        server.run(transport=args.transport)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
