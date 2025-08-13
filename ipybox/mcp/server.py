#!/usr/bin/env python3
import asyncio
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
    ):
        self.path_validator = PathValidator(allowed_dirs)
        self.container_config = container_config

        # These will be initialized in setup()
        self.container: ExecutionContainer | None = None
        self.execution_client: ExecutionClient | None = None
        self.resource_client: ResourceClient | None = None

        # Create FastMCP server
        self.mcp = FastMCP("ipybox")

        # Register tools
        self.mcp.tool()(self.execute_ipython_cell)
        self.mcp.tool()(self.upload_file)
        self.mcp.tool()(self.download_file)
        self.mcp.tool()(self.reset)

        self.setup_task: asyncio.Task = asyncio.create_task(self._setup())
        self.executor_lock = asyncio.Lock()

    async def _setup(self) -> None:
        """Initialize container and execution client."""
        self.container = ExecutionContainer(**self.container_config)
        await self.container.run()

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
            await self._cleanup()
