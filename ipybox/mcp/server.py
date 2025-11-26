import argparse
import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ipybox.kernel.executor import ExecutionClient
from ipybox.kernel.gateway import KernelGateway
from ipybox.mcp.apigen import generate_mcp_sources
from ipybox.mcp.runner.client import reset
from ipybox.mcp.runner.server import ToolServer
from ipybox.utils import find_free_port

logger = logging.getLogger(__name__)


class MCPServer:
    def __init__(
        self,
        tool_server_host: str = "localhost",
        tool_server_port: int | None = None,
        kernel_gateway_host: str = "localhost",
        kernel_gateway_port: int | None = None,
        sandbox: bool = False,
        sandbox_settings: Path | None = None,
        log_level: str = "INFO",
    ):
        self.tool_server_host = tool_server_host
        self.tool_server_port = tool_server_port or find_free_port()

        self.kernel_gateway_host = kernel_gateway_host
        self.kernel_gateway_port = kernel_gateway_port or find_free_port()

        self.sandbox = sandbox
        self.sandbox_settings = sandbox_settings
        self.log_level = log_level

        self._mcp = FastMCP("ipybox", lifespan=self.server_lifespan, log_level=log_level)
        self._mcp.tool(structured_output=False)(self.register_mcp_server)
        self._mcp.tool(structured_output=False)(self.install_package)
        self._mcp.tool(structured_output=False)(self.execute_ipython_cell)
        self._mcp.tool(structured_output=False)(self.reset)

        self._client: ExecutionClient
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
                sandbox_settings=self.sandbox_settings,
                log_to_stderr=True,
                log_level=self.log_level,
                env={
                    "TOOL_SERVER_HOST": self.tool_server_host,
                    "TOOL_SERVER_PORT": str(self.tool_server_port),
                },
            ):
                async with ExecutionClient(
                    host=self.kernel_gateway_host,
                    port=self.kernel_gateway_port,
                ) as client:
                    self._client = client
                    yield

    async def register_mcp_server(self, server_name: str, server_params: dict[str, Any]) -> list[str]:
        """Register an MCP server and generate Python client functions for its tools.

        Connects to an external MCP server, introspects its tools, and generates a Python
        package under mcptools/{server_name}/ with type-safe client functions. Generated
        tools are immediately available for import in execute_ipython_cell.

        Usage Pattern:
            from mcptools.{server_name} import {tool_name}
            result = {tool_name}.run({tool_name}.Params(arg1=value1, arg2=value2))

        Each generated tool module provides:
        - Params: Pydantic model for input parameters with type validation
        - Result: Pydantic model for output (only if MCP tool defines output schema)
        - run(params): Returns Result object if output schema exists, otherwise returns str

        Important Behaviors:
        - Re-registering the same server_name overwrites the previous registration
        - After re-registration, call reset() to enable re-importing of updated tool definitions
        - Environment variable placeholders like {BRAVE_API_KEY} in server_params are
          automatically replaced with actual environment values
        - Generated mcptools/ directory persists across reset() calls

        Configuration Examples:

        Stdio (local executable):
        {"command": "npx", "args": ["-y", "@some/mcp-server-package"],
         "env": {"API_KEY": "{API_KEY}"}}

        HTTP (remote API):
        {"url": "https://api.example.com/mcp/",
         "headers": {"Authorization": "Bearer {API_TOKEN}"}}

        Args:
            server_name: Unique identifier that becomes the package name under mcptools/.
                Must be a valid Python module name (lowercase, numbers, underscores;
                cannot start with number).
            server_params: MCP server configuration with either:
                - stdio: {"command": str, "args": list[str], "env": dict}
                - streamable-http or sse: {"url": str, "headers": dict}

        Returns:
            List of sanitized tool names available for import from mcptools.{server_name}.
            Tool names are converted to valid Python identifiers (lowercase, special
            characters replaced with underscores).
        """

        return await generate_mcp_sources(
            server_name=server_name,
            server_params=server_params,
            root_dir=Path("mcptools"),
        )

    async def install_package(self, package_name: str) -> str:
        """Install a Python package in the IPython kernel environment.

        Installs packages using pip within the kernel's Python environment. Installed
        packages are immediately available for import in subsequent execute_ipython_cell
        calls and persist across reset() calls.

        This is the required way to install packages.

        Package Installation Examples:
        - install_package("numpy") - Install latest version
        - install_package("pandas==2.0.0") - Install specific version
        - install_package("requests>=2.28.0") - Install with version constraint
        - install_package("git+https://github.com/user/repo.git") - Install from git

        Args:
            package_name: Package specification to install. Can be a simple package name,
                a package with version specifier (e.g., "numpy>=1.20.0"), or a URL to a
                git repository or wheel file.

        Returns:
            Installation output from pip, including success messages, warnings, and errors.
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
            Field(description="Maximum execution time in seconds before the kernel is interrupted"),
        ] = 120,
    ) -> str:
        """Execute Python code in a stateful IPython kernel.

        The kernel maintains state across executions - variables, imports, and function
        definitions persist between calls. Each execution builds on previous ones, enabling
        complex multi-step workflows. Executions are sequential (not concurrent) to maintain
        consistent kernel state.

        The kernel has an active asyncio event loop, so use 'await' directly for async code.
        DO NOT use asyncio.run() or create new event loops.

        Using Registered MCP Tools:
        Import and call tools registered via register_mcp_server():
            from mcptools.{server_name} import {tool_name}
            result = {tool_name}.run({tool_name}.Params(arg1=value1))

        Package Installation:
        Use the install_package() tool for installing packages, or include
        '!uv add package_name' or '!pip install package_name' directly in the code.

        Args:
            code: Python code to execute. Can include imports, definitions, expressions,
                and statements. Multi-line code blocks are supported.
            timeout: Maximum seconds to wait before interrupting execution. Default is 120
                seconds. If exceeded, the kernel is interrupted and asyncio.TimeoutError is
                raised. Increase for long-running computations or large data processing.

        Returns:
            String containing execution output (last expression value, stdout, stderr) and
                generated image file paths in markdown format (e.g., [image_id](path/to/image_id.png)).
                Returns empty string if no output was produced.

        Raises:
            ExecutionError: If code execution raises an exception. Includes exception type,
                message, and full traceback.
            ToolRunnerError: If a registered MCP tool call fails. Includes error details
                from the external tool.
            asyncio.TimeoutError: If execution exceeds the timeout duration.
        """
        async with self._lock:
            result = await self._client.execute(code, timeout=timeout)

            # -------------------------------------------------
            #  TODO: consider returning structured output
            # -------------------------------------------------

            output = result.text or ""
            if result.images:
                output += "\n\nGenerated images:\n\n"
                for img_path in result.images:
                    output += f"- [{img_path.stem}]({img_path.absolute()})\n"
            return output

    async def reset(self):
        """Reset the IPython kernel to a clean state.

        Creates a new kernel instance, clearing all variables, imports, and function
        definitions from memory. Use this when previous execution state is no longer needed
        or to start fresh experiments.

        What Gets Cleared:
        - All variables and their values
        - All imported modules and packages
        - All function and class definitions
        - All registered MCP server connections (auto-reconnect on next tool use)

        What Persists:
        - Installed packages (via install_package tool)
        - Files in the container filesystem
        - The mcptools/ directory and generated tool definitions

        After reset, you can immediately re-import tools from mcptools/ and they will
        reconnect to their MCP servers automatically.

        Common Use Cases:
        - Starting a new analysis or experiment from scratch
        - Clearing memory after processing large datasets
        - Re-importing updated tool definitions after re-registering an MCP server
        - Recovering from a problematic kernel state
        """
        async with self._lock:
            await reset(
                host=self.tool_server_host,
                port=self.tool_server_port,
            )
            await self._client.disconnect()
            self._client = ExecutionClient(
                host=self.kernel_gateway_host,
                port=self.kernel_gateway_port,
            )
            await self._client.connect()

    async def run(self):
        await self._mcp.run_stdio_async()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="IPyBox MCP Server - Provides IPython kernel execution via Model Context Protocol"
    )
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
        "--sandbox-settings",
        type=Path,
        default=None,
        help="Sandbox settings file (default: None)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level (default: INFO)",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()

    os.makedirs(args.workspace, exist_ok=True)
    os.chdir(args.workspace)

    server = MCPServer(
        tool_server_host=args.tool_server_host,
        tool_server_port=args.tool_server_port,
        kernel_gateway_host=args.kernel_gateway_host,
        kernel_gateway_port=args.kernel_gateway_port,
        sandbox=args.sandbox,
        sandbox_settings=args.sandbox_settings,
        log_level=args.log_level,
    )
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
