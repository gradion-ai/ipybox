import argparse
import asyncio
import logging
import os
import signal
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ipybox.kernel_mgr.client import KernelClient
from ipybox.kernel_mgr.server import KernelGateway
from ipybox.mcp_apigen import generate_mcp_sources
from ipybox.tool_exec.client import reset
from ipybox.tool_exec.server import ToolServer
from ipybox.utils import find_free_port

logger = logging.getLogger(__name__)

KERNEL_ENV_PREFIX = "KERNEL_ENV_"


class MCPServer:
    def __init__(
        self,
        tool_server_host: str = "localhost",
        tool_server_port: int | None = None,
        kernel_gateway_host: str = "localhost",
        kernel_gateway_port: int | None = None,
        kernel_env: dict[str, str] | None = None,
        sandbox: bool = False,
        sandbox_config: Path | None = None,
        log_level: str = "INFO",
    ):
        self.tool_server_host = tool_server_host
        self.tool_server_port = tool_server_port or find_free_port()

        self.kernel_gateway_host = kernel_gateway_host
        self.kernel_gateway_port = kernel_gateway_port or find_free_port()

        self.sandbox = sandbox
        self.sandbox_config = sandbox_config
        self.log_level = log_level
        self.kernel_env = kernel_env or {}

        self._mcp = FastMCP("ipybox", lifespan=self.server_lifespan, log_level=log_level)
        self._mcp.tool(structured_output=False)(self.register_mcp_server)
        self._mcp.tool(structured_output=False)(self.install_package)
        self._mcp.tool(structured_output=False)(self.execute_ipython_cell)
        self._mcp.tool(structured_output=False)(self.reset)

        self._client: KernelClient
        self._lock = asyncio.Lock()

    @asynccontextmanager
    async def server_lifespan(self, server: FastMCP):
        async with ToolServer(
            host=self.tool_server_host,
            port=self.tool_server_port,
            log_to_stderr=True,
            log_level=self.log_level,
        ):
            async with KernelGateway(
                host=self.kernel_gateway_host,
                port=self.kernel_gateway_port,
                sandbox=self.sandbox,
                sandbox_config=self.sandbox_config,
                log_to_stderr=True,
                log_level=self.log_level,
                env=self.kernel_env
                | {
                    "TOOL_SERVER_HOST": self.tool_server_host,
                    "TOOL_SERVER_PORT": str(self.tool_server_port),
                },
            ):
                async with KernelClient(
                    host=self.kernel_gateway_host,
                    port=self.kernel_gateway_port,
                ) as client:
                    self._client = client
                    yield

    async def register_mcp_server(self, server_name: str, server_params: dict[str, Any]) -> list[str]:
        """Register an MCP server and generate importable Python tool functions.

        Connects to an MCP server, generates a package at mcptools/{server_name}/ with
        type-safe client functions. Use generated tools via:
            from mcptools.{server_name} import {tool_name}
            result = {tool_name}.run({tool_name}.Params(...))

        - Environment variable placeholders like {API_KEY} in server_params are auto-replaced
        - Re-registering overwrites previous; call reset() to re-import updated tools
        - Generated mcptools/ persists across reset() calls

        Args:
            server_name: Package name (valid Python identifier: lowercase, underscores, no leading digit).
            server_params: Server config - stdio: {"command", "args", "env"} or http: {"url", "headers"}.

        Returns:
            List of tool names available for import from mcptools.{server_name}.
        """

        return await generate_mcp_sources(
            server_name=server_name,
            server_params=server_params,
            root_dir=Path("mcptools"),
        )

    async def install_package(self, package_name: str) -> str:
        """Install a Python package via pip.

        Installed packages persist across reset() calls and are immediately importable.
        Supports version specifiers (e.g., "numpy>=1.20.0") and git URLs.

        Args:
            package_name: Package spec (name, name==version, or git+https://... URL).

        Returns:
            Pip output including success messages, warnings, and errors.
        """
        import sys

        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-input",
            package_name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate()

        output = ""
        if stdout:
            output += stdout.decode()
        if stderr:
            output += stderr.decode()

        return output

    async def execute_ipython_cell(
        self,
        code: Annotated[
            str,
            Field(description="Python code to execute in the IPython kernel"),
        ],
        timeout: Annotated[
            float,
            Field(description="Maximum execution time in seconds before kernel interruption"),
        ] = 120,
        max_output_chars: Annotated[
            int,
            Field(description="Maximum number of characters to return in output (truncates if exceeded)"),
        ] = 5000,
    ) -> str:
        """Execute Python code in a stateful IPython kernel.

        State (variables, imports, definitions) persists across calls. Executions are sequential.
        For async code, use 'await' directly (kernel has an active event loop).

        Returns:
            Execution output (stdout, stderr, last expression) plus image paths as markdown links.
            Empty string if no output.

        Raises:
            ExecutionError: Code raised an exception (includes traceback).
            ToolRunnerError: MCP tool call failed.
            asyncio.TimeoutError: Execution exceeded timeout.
        """
        async with self._lock:
            result = await self._client.execute(code, timeout=timeout)
            output = result.text or ""
            if result.images:
                output += "\n\nGenerated images:\n\n"
                for img_path in result.images:
                    output += f"- [{img_path.stem}]({img_path.absolute()})\n"

            if len(output) > max_output_chars:
                output = (
                    output[:max_output_chars] + f"\n\n[Output truncated: exceeded {max_output_chars} character limit]"
                )

            return output

    async def reset(self):
        """Reset the IPython kernel to a clean state.

        Creates a new kernel, clearing all variables, imports, and definitions.

        - Cleared: all in-memory state, MCP server connections (auto-reconnect on next use)
        - Persists: installed packages, filesystem files, mcptools/ directory
        """
        async with self._lock:
            await reset(
                host=self.tool_server_host,
                port=self.tool_server_port,
            )
            await self._client.reset()

    async def run(self):
        await self._mcp.run_stdio_async()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ipybox MCP Server")
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path("."),
        help="Code workspace (default: .)",
    )
    parser.add_argument(
        "--tool-server-host",
        type=str,
        default="localhost",
        help="Tool server host (default: localhost)",
    )
    parser.add_argument(
        "--tool-server-port",
        type=int,
        default=None,
        help="Tool server port (default: dynamic)",
    )
    parser.add_argument(
        "--kernel-gateway-host",
        type=str,
        default="localhost",
        help="Kernel gateway host (default: localhost)",
    )
    parser.add_argument(
        "--kernel-gateway-port",
        type=int,
        default=None,
        help="Kernel gateway port (default: dynamic)",
    )
    parser.add_argument(
        "--sandbox",
        action="store_true",
        help="Run kernel gateway in sandbox",
    )
    parser.add_argument(
        "--sandbox-config",
        type=Path,
        default=None,
        help="Sandbox config file (default: None)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level (default: INFO)",
    )
    return parser.parse_args()


def extract_kernel_env() -> dict[str, str]:
    kernel_env = {}

    for key, value in os.environ.items():
        if key.startswith(KERNEL_ENV_PREFIX):
            kernel_env[key[len(KERNEL_ENV_PREFIX) :]] = value

    return kernel_env


async def main():
    args = parse_args()

    os.makedirs(args.workspace, exist_ok=True)
    os.chdir(args.workspace)

    load_dotenv(args.workspace.absolute() / ".env")

    sandbox_config = None

    if args.sandbox_config:
        if args.sandbox_config.exists():
            sandbox_config = args.sandbox_config
        else:
            logger.warning(f"Sandbox config file {args.sandbox_config} does not exist, Using default config")

    server = MCPServer(
        tool_server_host=args.tool_server_host,
        tool_server_port=args.tool_server_port,
        kernel_gateway_host=args.kernel_gateway_host,
        kernel_gateway_port=args.kernel_gateway_port,
        sandbox=args.sandbox,
        sandbox_config=sandbox_config,
        log_level=args.log_level,
        kernel_env=extract_kernel_env(),
    )

    loop = asyncio.get_running_loop()

    def handle_signal():
        for task in asyncio.all_tasks(loop):
            task.cancel()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, handle_signal)

    await server.run()


def cli():
    asyncio.run(main())


if __name__ == "__main__":
    cli()
