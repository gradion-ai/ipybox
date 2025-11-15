#!/usr/bin/env python3
import asyncio
import logging
from pathlib import Path
from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ipybox import ExecutionClient, ExecutionContainer, ExecutionError, ResourceClient


class PathValidator:
    """Validates host filesystem paths against a whitelist."""

    def __init__(self, allowed_dirs: list[Path]):
        self.allowed_dirs = [Path(d).resolve() for d in allowed_dirs]

    def validate(self, path: Path, operation: str = "access") -> None:
        """Validate a path or raise an error."""
        if not self._allowed(path):
            raise PermissionError(f"Path '{path}' is not within allowed directories for {operation}")

    def _allowed(self, path: Path) -> bool:
        """Check if a path is within any of the allowed directories."""
        try:
            resolved = Path(path).resolve()
            return any(resolved == allowed or resolved.is_relative_to(allowed) for allowed in self.allowed_dirs)
        except (OSError, ValueError):
            return False


class MCPServer:
    def __init__(
        self,
        allowed_dirs: list[Path],
        container_config: dict[str, Any],
        allowed_domains: list[str] | None = None,
        log_level: str = "WARNING",
    ):
        # Configure logging
        logging.basicConfig(level=getattr(logging, log_level.upper()))

        self.path_validator = PathValidator(allowed_dirs)
        self.container_config = container_config
        self.allowed_domains = allowed_domains

        # These will be initialized in setup()
        self.container: ExecutionContainer | None = None
        self.execution_client: ExecutionClient | None = None
        self.resource_client: ResourceClient | None = None

        # Create FastMCP server
        self.mcp = FastMCP("ipybox")

        # Register tools
        self.mcp.tool(structured_output=False)(self.execute_ipython_cell)
        self.mcp.tool(structured_output=False)(self.upload_file)
        self.mcp.tool(structured_output=False)(self.download_file)
        self.mcp.tool(structured_output=False)(self.reset)
        self.mcp.tool(structured_output=False)(self.register_mcp_server)
        self.mcp.tool(structured_output=False)(self.get_mcp_server_names)
        self.mcp.tool(structured_output=False)(self.get_mcp_tool_descriptions)
        self.mcp.tool(structured_output=False)(self.get_mcp_tool_sources)

        self.setup_task: asyncio.Task = asyncio.create_task(self._setup())
        self.executor_lock = asyncio.Lock()

    async def _setup(self) -> None:
        """Initialize container and execution client."""
        self.container = ExecutionContainer(**self.container_config)
        await self.container.run()

        # Initialize firewall if allowed domains are specified
        if self.allowed_domains is not None:
            await self.container.init_firewall(self.allowed_domains)

        self.execution_client = ExecutionClient(port=self.container.executor_port)
        await self.execution_client.connect()

        self.resource_client = ResourceClient(port=self.container.resource_port)
        await self.resource_client.connect()

    async def _cleanup(self) -> None:
        if self.execution_client:
            await self.execution_client.disconnect()

        if self.resource_client:
            await self.resource_client.disconnect()

        if self.container:
            await self.container.kill()

    async def reset(self):
        """Reset the IPython kernel to a clean state.

        Creates a new kernel instance, clearing all variables, imports, and definitions
        from memory. Installed packages and files in the container filesystem are
        preserved. Useful for starting fresh experiments or clearing memory after
        processing large datasets.
        """
        await self.setup_task
        assert self.container is not None
        assert self.execution_client is not None

        async with self.executor_lock:
            await self.execution_client.disconnect()

            self.execution_client = ExecutionClient(port=self.container.executor_port)
            await self.execution_client.connect()

    async def register_mcp_server(self, server_name: str, server_params: dict[str, Any]) -> list[str]:
        """Register an MCP server and make its tools available as Python functions in the IPython kernel.

        This tool connects to an external MCP server, introspects its available tools, and generates
        Python client functions that can be imported and used in execute_ipython_cell. After registration,
        the generated functions are saved to the container's filesystem and can be imported like any
        standard Python module.

        IMPORTANT: Environment variable placeholders in server_params (like {BRAVE_API_KEY} or
        {GITHUB_API_KEY}) will be automatically replaced with actual values from the environment
        where ipybox is running.

        Configuration Examples:

        For stdio-based MCP servers (local executables):
        {
            "command": "npx",
            "args": ["-y", "@brave/brave-search-mcp-server", "--transport", "stdio"],
            "env": {
                "BRAVE_API_KEY": "{BRAVE_API_KEY}"
            }
        }

        For streamable-http based MCP servers (remote APIs):
        {
            "url": "https://api.githubcopilot.com/mcp/",
            "headers": {
                "Authorization": "Bearer {GITHUB_API_KEY}"
            }
        }

        After registration, the generated Python functions can be imported and used:
        ```python
        from mcpgen.{server_name}.tool_name import run, Params
        result = run(params=Params(param1="value1", param2="value2"))
        ```

        Args:
            server_name: Unique identifier for this MCP server (must be a valid Python module name)
            server_params: MCP server configuration dictionary with command/args (stdio) or url/headers (http)

        Returns:
            List of tool names that were registered and are now available as Python functions
        """
        await self.setup_task
        assert self.resource_client is not None

        return await self.resource_client.generate_mcp_sources(
            relpath="mcpgen",
            server_name=server_name,
            server_params=server_params,
        )

    async def get_mcp_server_names(self) -> list[str]:
        """List all MCP servers that have been registered and have generated Python client code.

        After registering MCP servers with register_mcp_server, use this tool to discover which
        servers are available. The returned server names can then be used with get_mcp_tool_descriptions
        to explore what tools each server provides.

        Typical workflow:
        1. Call get_mcp_server_names to see available servers
        2. For each server, call get_mcp_tool_descriptions to see available tools
        3. Select the tools you need and call get_mcp_tool_sources to get their Python code
        4. Use the code in execute_ipython_cell to invoke the tools

        Returns:
            List of registered MCP server names (e.g., ["brave_search", "github", "filesystem"])
        """
        await self.setup_task
        assert self.resource_client is not None

        return await self.resource_client.get_mcp_server_names("mcpgen")

    async def get_mcp_tool_descriptions(self, server_name: str) -> dict[str, str]:
        """Get descriptions of all tools available from a specific MCP server.

        Use this tool to discover what capabilities a registered MCP server provides. The returned
        descriptions help you understand each tool's purpose so you can select which tools to use
        for your task. Once you've identified the tools you need, use get_mcp_tool_sources to
        retrieve their Python implementation code.

        The descriptions are extracted from the MCP server's tool schemas and explain what each
        tool does, what parameters it accepts, and what it returns.

        Example workflow:
        ```
        servers = get_mcp_server_names()
        # Returns: ["brave_search", "github"]

        descriptions = get_mcp_tool_descriptions("brave_search")
        # Returns: {"web_search": "Search the web using Brave Search API...", ...}

        # Now you know brave_search has a web_search tool, get its code:
        sources = get_mcp_tool_sources("brave_search", ["web_search"])
        ```

        Args:
            server_name: Name of the registered MCP server to query (from get_mcp_server_names)

        Returns:
            Dictionary mapping tool names to their descriptions (e.g., {"web_search": "Search the web...", "local_search": "Search locally..."})
        """
        await self.setup_task
        assert self.resource_client is not None

        return await self.resource_client.get_mcp_descriptions("mcpgen", server_name)

    async def get_mcp_tool_sources(self, server_name: str, tool_names: list[str] | None = None) -> dict[str, str]:
        """Retrieve the generated Python source code for specific MCP tools.

        After discovering available tools with get_mcp_tool_descriptions, use this tool to retrieve
        the actual Python implementation code for the tools you want to use. The returned code
        contains ready-to-use Python functions that you can execute with execute_ipython_cell to
        invoke the MCP tools.

        Each tool's source code includes:
        - A typed Pydantic model (Params) for tool parameters
        - A run() function that executes the tool with the given parameters
        - All necessary imports and type hints

        The generated code is designed to be executed directly in the IPython kernel.

        Example usage:
        ```
        # Get the source code for web_search tool to understand its interface
        sources = get_mcp_tool_sources("brave_search", ["web_search"])
        # Returns: {"web_search": "from pydantic import BaseModel\\nclass Params(BaseModel):\\n..."}

        # The sources are already on sys.path, just import and use them:
        execute_ipython_cell('''
        from mcpgen.brave_search.web_search import run, Params
        result = run(params=Params(query="Python tutorials"))
        print(result)
        ''')
        ```

        Args:
            server_name: Name of the registered MCP server (from get_mcp_server_names)
            tool_names: List of specific tool names to retrieve, or None to retrieve all tools from the server

        Returns:
            Dictionary mapping tool names to their Python source code
        """
        await self.setup_task
        assert self.resource_client is not None

        # Get all tool sources for the server
        all_sources = await self.resource_client.get_mcp_sources("mcpgen", server_name)

        # If tool_names is None, return all sources
        if tool_names is None:
            return all_sources

        # Filter to only requested tools
        result: dict[str, str] = {}
        for tool_name in tool_names:
            if tool_name in all_sources:
                result[tool_name] = all_sources[tool_name]

        return result

    async def execute_ipython_cell(
        self,
        code: Annotated[
            str,
            Field(description="Python code to execute in the IPython kernel"),
        ],
        timeout: Annotated[
            float, Field(description="Maximum execution time in seconds before the kernel is interrupted")
        ] = 120,
    ) -> str:
        """Execute Python code in a stateful IPython kernel within a Docker container.

        The kernel maintains state across executions - variables, imports, and definitions
        persist between calls. Each execution builds on the previous one, allowing you to
        build complex workflows step by step. Use '!pip install package_name' to install
        packages as needed.

        The kernel has an active asyncio event loop, so use 'await' directly for async
        code. DO NOT use asyncio.run() or create new event loops.

        Executions are sequential (not concurrent) as they share kernel state. Use the
        reset() tool to clear the kernel state and start fresh.

        Returns:
            str: Output text from execution, or empty string if no output.
        """
        await self.setup_task
        assert self.execution_client is not None

        try:
            async with self.executor_lock:
                result = await self.execution_client.execute(code, timeout=timeout)
                return result.text or ""
        except Exception as e:
            match e:
                case ExecutionError():
                    raise ExecutionError(e.args[0] + "\n" + e.trace)
                case _:
                    raise e

    async def upload_file(
        self,
        relpath: Annotated[
            str,
            Field(
                description="Destination path relative to container's /app directory (e.g., 'data/input.csv' saves to /app/data/input.csv)"
            ),
        ],
        local_path: Annotated[
            str, Field(description="Absolute path to the source file on host filesystem that will be uploaded")
        ],
    ):
        """Upload a file from the host filesystem to the container's /app directory.

        Makes a file from the host available inside the container for code execution.
        The uploaded file can then be accessed in execute_ipython_cell using the
        path '/app/{relpath}'.
        """
        await self.setup_task
        assert self.resource_client is not None

        local_path_obj = Path(local_path)
        self.path_validator.validate(local_path_obj, "upload")

        if not local_path_obj.exists():
            raise FileNotFoundError(f"File not found: {local_path_obj}")

        if not local_path_obj.is_file():
            raise ValueError(f"Not a file: {local_path_obj}")

        await self.resource_client.upload_file(relpath, local_path_obj)

    async def download_file(
        self,
        relpath: Annotated[
            str,
            Field(
                description="Source path relative to container's /app directory (e.g., 'output/results.csv' reads from /app/output/results.csv)"
            ),
        ],
        local_path: Annotated[str, Field(description="Absolute path on host filesystem where the file will be saved")],
    ):
        """Download a file from the container's /app directory to the host filesystem.

        Retrieves files created or modified during code execution from the container.
        The file at '/app/{relpath}' in the container will be saved to the specified
        location on the host.

        Parent directories are created automatically if they don't exist.
        """
        await self.setup_task
        assert self.resource_client is not None

        local_path_obj = Path(local_path)
        self.path_validator.validate(local_path_obj, "download")
        local_path_obj.parent.mkdir(parents=True, exist_ok=True)

        await self.resource_client.download_file(relpath, local_path_obj)

    async def run(self):
        try:
            await self.mcp.run_stdio_async()
        finally:
            await self.setup_task
            await self._cleanup()
