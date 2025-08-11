#!/usr/bin/env python3
"""MCP server for ipybox - provides secure Python code execution via Docker containers."""

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from time import perf_counter
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from ipybox import ExecutionClient, ExecutionContainer, ResourceClient


class PathSecurity:
    """Manages host filesystem path validation against a whitelist."""

    def __init__(self, allowed_dirs: list[Path]):
        self.allowed_dirs = [Path(d).resolve() for d in allowed_dirs]

    def is_allowed(self, path: Path) -> bool:
        """Check if a path is within any of the allowed directories."""
        try:
            resolved = Path(path).resolve()
            return any(resolved == allowed or resolved.is_relative_to(allowed) for allowed in self.allowed_dirs)
        except (OSError, ValueError):
            return False

    def validate(self, path: Path, operation: str = "access") -> None:
        """Validate a path or raise an error."""
        if not self.is_allowed(path):
            raise PermissionError(f"Path '{path}' is not within allowed directories for {operation}")


class IpyboxMCPServer:
    """MCP server implementation for ipybox using FastMCP."""

    def __init__(
        self,
        allowed_dirs: list[Path],
        default_images_dir: Path,
        container_config: dict[str, Any],
        log_file: Path,
    ):
        self.path_security = PathSecurity(allowed_dirs)
        self.default_images_dir = default_images_dir
        self.container_config = container_config
        self.log_file = log_file

        # These will be initialized in setup()
        self.container: Optional[ExecutionContainer] = None
        self.execution_client: Optional[ExecutionClient] = None
        self.resource_client: Optional[ResourceClient] = None

        # Setup logging
        self._setup_logging()
        self.logger = logging.getLogger(__name__)

        # Create FastMCP server
        self.mcp = FastMCP("ipybox")

        # Register tools
        self.mcp.tool()(self.reset)
        self.mcp.tool()(self.execute_ipython_cell)
        self.mcp.tool()(self.upload_file)
        self.mcp.tool()(self.download_file)

    def _setup_logging(self) -> None:
        """Configure logging to file."""
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(self.log_file),
                logging.StreamHandler(sys.stderr),
            ],
        )

    async def setup(self) -> None:
        """Initialize container and execution client."""
        self.logger.info("Starting ipybox container")
        self.container = ExecutionContainer(**self.container_config)
        await self.container.__aenter__()

        # Create and connect the single execution client
        self.execution_client = ExecutionClient(port=self.container.executor_port)
        await self.execution_client.connect()

        # Add /app to Python path for the kernel
        await self.execution_client.execute("import sys; sys.path.insert(0, '/app')")

        self.resource_client = ResourceClient(port=self.container.resource_port)
        await self.resource_client.connect()

        self.logger.info(
            f"Container started - executor port: {self.container.executor_port}, "
            f"resource port: {self.container.resource_port}"
        )

    async def cleanup(self) -> None:
        """Clean up resources."""
        self.logger.info("Cleaning up ipybox MCP server")

        if self.execution_client:
            await self.execution_client.disconnect()

        if self.resource_client:
            await self.resource_client.disconnect()

        if self.container:
            await self.container.__aexit__(None, None, None)

        self.logger.info("Cleanup complete")

    def _register_tools(self) -> None:
        """Register all MCP tools with the FastMCP server."""

    async def reset(self) -> dict[str, str]:
        """Reset the IPython kernel by disconnecting and creating a new one."""
        assert self.execution_client is not None
        assert self.container is not None

        self.logger.info("Resetting IPython kernel")

        # Disconnect current client
        await self.execution_client.disconnect()

        # Create and connect new client
        self.execution_client = ExecutionClient(port=self.container.executor_port)
        await self.execution_client.connect()

        # Add /app to Python path for the kernel
        await self.execution_client.execute("import sys; sys.path.insert(0, '/app')")

        self.logger.info("Kernel reset complete")
        return {"status": "success"}

    async def execute_ipython_cell(self, code: str, images_dir: Optional[str] = None) -> dict[str, Any]:
        """Execute Python code in the IPython kernel.

        Args:
            code: Python code to execute
            images_dir: Local host directory for saving generated images (optional)
        """
        assert self.execution_client is not None

        # Determine images directory
        if images_dir is not None:
            img_dir = Path(images_dir)
        else:
            img_dir = self.default_images_dir

        # Validate images directory
        self.path_security.validate(img_dir, "save images")
        img_dir.mkdir(parents=True, exist_ok=True)

        # Execute code

        # Process results
        result: dict[str, Any] = {
            "text": None,
            "images": [],
        }

        try:
            exec_result = await self.execution_client.execute(code)

            # Set text output
            if exec_result.text:
                result["text"] = exec_result.text

            # Save images
            for i, image in enumerate(exec_result.images):
                timestamp = int(asyncio.get_event_loop().time() * 1000)
                filename = f"ipybox_{timestamp}_{i}.png"
                image_path = img_dir / filename

                # Save PIL image
                image.save(image_path, "PNG")
                result["images"].append(str(image_path))
                self.logger.info(f"Saved image to {image_path}")

        except Exception as e:
            # Import ExecutionError to handle it properly
            from ipybox.executor import ExecutionError

            if isinstance(e, ExecutionError):
                # Python execution error - include in output text
                error_text = str(e)
                if e.trace:
                    error_text += f"\n{e.trace}"
                result["text"] = error_text
            else:
                # Other error - re-raise to become MCP error
                raise

        return result

    async def upload_file(self, relpath: str, local_path: str) -> dict[str, str]:
        """Upload a file from host to container.

        Args:
            relpath: Path relative to container's /app directory
            local_path: Absolute path to file on host filesystem
        """
        assert self.resource_client is not None

        # Validate host path
        local_path_obj = Path(local_path)
        self.path_security.validate(local_path_obj, "upload")

        if not local_path_obj.exists():
            raise FileNotFoundError(f"File not found: {local_path_obj}")

        if not local_path_obj.is_file():
            raise ValueError(f"Not a file: {local_path_obj}")

        # Upload file
        await self.resource_client.upload_file(relpath, local_path_obj)
        self.logger.info(f"Uploaded {local_path_obj} to container:{relpath}")
        return {"status": "success"}

    async def download_file(self, relpath: str, local_path: str) -> dict[str, str]:
        """Download a file from container to host.

        Args:
            relpath: Path relative to container's /app directory
            local_path: Absolute path for saving on host filesystem
        """
        assert self.resource_client is not None

        # Validate host path
        local_path_obj = Path(local_path)
        self.path_security.validate(local_path_obj, "download")

        # Create parent directory if needed
        local_path_obj.parent.mkdir(parents=True, exist_ok=True)

        # Download file
        await self.resource_client.download_file(relpath, local_path_obj)
        self.logger.info(f"Downloaded container:{relpath} to {local_path_obj}")
        return {"status": "success"}

    def run(self, transport: str = "stdio") -> None:
        """Run the MCP server."""

        async def run_async():
            setup_start = perf_counter()
            await self.setup()
            setup_duration_s = perf_counter() - setup_start
            self.logger.info(f"----- Setup completed in {setup_duration_s:.3f}s -----")
            try:
                self.logger.info("MCP server ready")
                if transport == "stdio":
                    await self.mcp.run_stdio_async()
                elif transport == "sse":
                    await self.mcp.run_sse_async()
                elif transport == "streamable-http":
                    await self.mcp.run_streamable_http_async()
                else:
                    raise ValueError(f"Unsupported transport: {transport}")
            finally:
                cleanup_start = perf_counter()
                await self.cleanup()
                cleanup_duration_s = perf_counter() - cleanup_start
                self.logger.info(f"----- Cleanup completed in {cleanup_duration_s:.3f}s -----")

        asyncio.run(run_async())


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="ipybox MCP Server - Secure Python code execution via Docker",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # Host path security
    parser.add_argument(
        "--allowed-dirs",
        nargs="+",
        default=[Path.home(), Path("/tmp")],
        type=Path,
        help="Directories allowed for host filesystem operations",
    )

    # Images directory
    parser.add_argument(
        "--images-dir",
        type=Path,
        default=Path.cwd() / "images",
        help="Default directory for saving generated images",
    )

    # Container configuration
    parser.add_argument(
        "--container-tag",
        default="gradion-ai/ipybox",
        help="Docker image tag for the ipybox container",
    )

    parser.add_argument(
        "--container-env",
        nargs="*",
        default=[],
        help="Environment variables for container (format: KEY=VALUE)",
    )

    parser.add_argument(
        "--container-binds",
        nargs="*",
        default=[],
        help="Bind mounts for container (format: host_path:container_path)",
    )

    parser.add_argument(
        "--executor-port",
        type=int,
        help="Host port for executor service (random if not specified)",
    )

    parser.add_argument(
        "--resource-port",
        type=int,
        help="Host port for resource service (random if not specified)",
    )

    # Logging
    parser.add_argument(
        "--log-file",
        type=Path,
        default=Path("./logs/mcp-ipybox.log"),
        help="Path to log file",
    )

    # Transport
    parser.add_argument(
        "--transport",
        "-t",
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
        help="Transport type to use",
    )

    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()

    # Parse environment variables
    env = {}
    for env_str in args.container_env:
        if "=" in env_str:
            key, value = env_str.split("=", 1)
            env[key] = value

    # Parse bind mounts
    binds = {}
    for bind_str in args.container_binds:
        if ":" in bind_str:
            host_path, container_path = bind_str.split(":", 1)
            binds[host_path] = container_path

    # Container configuration
    container_config = {
        "tag": args.container_tag,
        "env": env,
        "binds": binds,
        "executor_port": args.executor_port,
        "resource_port": args.resource_port,
    }

    # Create and run server
    server = IpyboxMCPServer(
        allowed_dirs=args.allowed_dirs,
        default_images_dir=args.images_dir,
        container_config=container_config,
        log_file=args.log_file,
    )

    server.run(transport=args.transport)


if __name__ == "__main__":
    main()
