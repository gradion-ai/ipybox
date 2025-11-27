import asyncio
import os
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Any, AsyncIterator

from mcp import ClientSession, StdioServerParameters, Tool
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import ContentBlock, TextContent

from ipybox.vars import replace_variables

ToolResult = dict[str, Any] | str | None


class MCPClient:
    def __init__(
        self,
        server_params: dict[str, Any],
        connect_timeout: float = 10,
    ):
        self.connect_timeout = connect_timeout
        self.server_params = replace_variables(server_params, os.environ).replaced

        self._session: ClientSession | None = None
        self._exit_stack = AsyncExitStack()

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.stop()

    @property
    def session(self) -> ClientSession:
        if not self._session:
            raise RuntimeError("MCP client not started")
        return self._session

    async def start(self):
        self._session = await self._exit_stack.enter_async_context(self._mcp_session())

    async def stop(self):
        try:
            await self._exit_stack.aclose()
        except RuntimeError:
            pass
        finally:
            self._session = None

    async def list_tools(self) -> list[Tool]:
        return (await self.session.list_tools()).tools

    async def run(self, tool_name: str, tool_args: dict[str, Any]) -> ToolResult:
        result = await self.session.call_tool(tool_name, arguments=tool_args)

        if result.isError:
            raise Exception(self._extract_text(result.content))

        if result.structuredContent:
            return result.structuredContent

        if content := result.content:
            return self._extract_text(content) or None

        return None

    def _extract_text(self, content: list[ContentBlock]) -> str:
        text_elems = []
        for elem in content:
            if isinstance(elem, TextContent):
                text_elems.append(elem.text)
        return "\n".join(text_elems)

    @asynccontextmanager
    async def _mcp_session(self) -> AsyncIterator[ClientSession]:
        async with self._mcp_client() as (read, write, *_):
            async with ClientSession(read, write) as session:
                await asyncio.wait_for(session.initialize(), timeout=self.connect_timeout)
                yield session

    def _mcp_client(self):
        if "command" in self.server_params:
            return stdio_client(StdioServerParameters(**self.server_params))
        elif "url" in self.server_params:
            url = self.server_params["url"]
            kwargs = {k: v for k, v in self.server_params.items() if k not in ["url", "type"]}

            if "/mcp" in url or self.server_params.get("type") == "streamable_http":
                return streamablehttp_client(url, **kwargs)
            elif "/sse" in url or self.server_params.get("type") == "sse":
                return sse_client(url, **kwargs)
            else:
                raise ValueError(
                    f"Unable to determine MCP client type from URL: {url}. "
                    "URL should contain '/mcp' or '/sse', or specify 'type' "
                    "as 'streamable_http' or 'sse'."
                )
        else:
            raise ValueError(f'Neither a "command" nor a "url" key in server_params: {self.server_params}')
