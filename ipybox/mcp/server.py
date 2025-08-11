#!/usr/bin/env python3
"""MCP server for ipybox - provides secure Python code execution via Docker containers."""

import argparse
import asyncio
import logging
from pathlib import Path
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from ipybox import ExecutionClient, ExecutionContainer, ResourceClient

logger = logging.getLogger(__name__)


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
    ):
        self.path_security = PathSecurity(allowed_dirs)
        self.default_images_dir = default_images_dir
        self.container_config = container_config

        # These will be initialized in setup()
        self.container: ExecutionContainer
        self.execution_client: ExecutionClient
        self.resource_client: ResourceClient

        # Create FastMCP server
        self.mcp = FastMCP("ipybox")

        # Register tools
        self.mcp.tool()(self.reset)
        self.mcp.tool()(self.execute_ipython_cell)
        self.mcp.tool()(self.upload_file)
        self.mcp.tool()(self.download_file)

        self.setup_task: asyncio.Task = asyncio.create_task(self._setup())
        self.executor_lock = asyncio.Lock()

    async def _setup(self) -> None:
        """Initialize container and execution client."""
        logger.info("Starting ipybox")
        self.container = ExecutionContainer(**self.container_config)
        await self.container.run()

        self.execution_client = ExecutionClient(port=self.container.executor_port)
        await self.execution_client.connect()

        self.resource_client = ResourceClient(port=self.container.resource_port)
        await self.resource_client.connect()

        logger.info(
            f"ipybox started - executor port: {self.container.executor_port}, "
            f"resource port: {self.container.resource_port}"
        )

    async def _cleanup(self) -> None:
        """Clean up resources."""
        logger.info("Cleaning up ipybox")

        if self.execution_client:
            await self.execution_client.disconnect()

        if self.resource_client:
            await self.resource_client.disconnect()

        if self.container:
            await self.container.kill()

        logger.info("Cleanup complete")

    async def reset(self) -> dict[str, str]:
        """Reset the IPython kernel by disconnecting and creating a new one."""
        await self.setup_task

        async with self.executor_lock:
            logger.info("Resetting IPython kernel")

            await self.execution_client.disconnect()

            self.execution_client = ExecutionClient(port=self.container.executor_port)
            await self.execution_client.connect()

            logger.info("Kernel reset complete")
            return {"status": "success"}

    async def execute_ipython_cell(self, code: str, images_dir: Optional[str] = None) -> dict[str, Any]:
        """Execute Python code in the IPython kernel.

        Args:
            code: Python code to execute
            images_dir: Local host directory for saving generated images (optional)
        """
        await self.setup_task

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
            async with self.executor_lock:
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
                logger.info(f"Saved image to {image_path}")

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
        await self.setup_task

        local_path_obj = Path(local_path)
        self.path_security.validate(local_path_obj, "upload")

        if not local_path_obj.exists():
            raise FileNotFoundError(f"File not found: {local_path_obj}")

        if not local_path_obj.is_file():
            raise ValueError(f"Not a file: {local_path_obj}")

        await self.resource_client.upload_file(relpath, local_path_obj)
        return {"status": "success"}

    async def download_file(self, relpath: str, local_path: str) -> dict[str, str]:
        """Download a file from container to host.

        Args:
            relpath: Path relative to container's /app directory
            local_path: Absolute path for saving on host filesystem
        """
        await self.setup_task

        # Validate host path
        local_path_obj = Path(local_path)
        self.path_security.validate(local_path_obj, "download")

        # Create parent directory if needed
        local_path_obj.parent.mkdir(parents=True, exist_ok=True)

        # Download file
        await self.resource_client.download_file(relpath, local_path_obj)
        return {"status": "success"}

    async def run(self):
        try:
            await self.mcp.run_stdio_async()
        finally:
            await self._cleanup()


def parse_args():
    parser = argparse.ArgumentParser(
        description="ipybox MCP Server",
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

    return parser.parse_args()


async def main():
    args = parse_args()

    env = {}
    for env_str in args.container_env:
        if "=" in env_str:
            key, value = env_str.split("=", 1)
            env[key] = value

    binds = {}
    for bind_str in args.container_binds:
        if ":" in bind_str:
            host_path, container_path = bind_str.split(":", 1)
            binds[host_path] = container_path

    container_config = {
        "tag": args.container_tag,
        "env": env,
        "binds": binds,
    }

    server = IpyboxMCPServer(
        allowed_dirs=args.allowed_dirs,
        default_images_dir=args.images_dir,
        container_config=container_config,
    )

    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
