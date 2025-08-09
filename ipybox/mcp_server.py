"""MCP server for ipybox - provides remote code execution as MCP tools."""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

from fastmcp import FastMCP

from ipybox.container import ExecutionContainer
from ipybox.executor import ExecutionClient, ExecutionError, ExecutionResult

logger = logging.getLogger(__name__)


@dataclass
class Session:
    """Represents an active execution session with its container and client."""

    session_id: str
    container: ExecutionContainer
    client: ExecutionClient
    created_at: float
    last_activity: float
    timeout: float

    async def execute(self, code: str, timeout: float = 120.0) -> ExecutionResult:
        """Execute code in this session's IPython kernel."""
        self.last_activity = time.time()
        return await self.client.execute(code, timeout=timeout)

    async def upload_file(self, file_path: str, content: bytes) -> Dict:
        """Upload a file to the session's container filesystem."""
        self.last_activity = time.time()
        # Use the resource server port to upload files
        import aiohttp

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"http://localhost:{self.container.resource_port}/files/{file_path}", data=content
            ) as response:
                response.raise_for_status()
                return await response.json()

    async def download_file(self, file_path: str) -> bytes:
        """Download a file from the session's container filesystem."""
        self.last_activity = time.time()
        import aiohttp

        async with aiohttp.ClientSession() as session:
            async with session.get(f"http://localhost:{self.container.resource_port}/files/{file_path}") as response:
                response.raise_for_status()
                return await response.read()

    async def list_files(self, directory_path: str) -> List[Dict]:
        """List files in a directory within the container."""
        self.last_activity = time.time()
        import aiohttp

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"http://localhost:{self.container.resource_port}/files/{directory_path}", params={"action": "list"}
            ) as response:
                response.raise_for_status()
                return await response.json()

    async def cleanup(self) -> None:
        """Clean up the session by disconnecting client and killing container."""
        try:
            await self.client.disconnect()
        except Exception as e:
            logger.warning(f"Error disconnecting client: {e}")

        try:
            await self.container.kill()
        except Exception as e:
            logger.warning(f"Error killing container: {e}")


class SessionManager:
    """Manages execution sessions and their lifecycles."""

    def __init__(
        self,
        session_timeout: float = 3600,  # 1 hour default
        max_concurrent_sessions: int = 10,
        cleanup_interval: float = 300,  # 5 minutes
    ):
        self.sessions: Dict[str, Session] = {}
        self.session_timeout = session_timeout
        self.max_concurrent_sessions = max_concurrent_sessions
        self._cleanup_task: Optional[asyncio.Task] = None
        self._cleanup_interval = cleanup_interval

    async def start(self) -> None:
        """Start the session manager background tasks."""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_expired_sessions())

    async def stop(self) -> None:
        """Stop the session manager and cleanup all sessions."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        # Cleanup all remaining sessions
        for session in list(self.sessions.values()):
            await session.cleanup()
        self.sessions.clear()

    async def create_session(
        self,
        session_id: str,
        image: str = "gradion-ai/ipybox-test",
        env_vars: Optional[Dict[str, str]] = None,
        timeout_seconds: Optional[int] = None,
        memory_limit: str = "512m",
        cpu_limit: str = "1",
    ) -> Session:
        """Create a new execution session."""
        # Use manager's default timeout if not specified
        if timeout_seconds is None:
            timeout_seconds = int(self.session_timeout)

        # Enforce session limits
        if len(self.sessions) >= self.max_concurrent_sessions:
            raise ValueError(f"Maximum concurrent sessions ({self.max_concurrent_sessions}) exceeded")

        if session_id in self.sessions:
            raise ValueError(f"Session {session_id} already exists")

        # Create container
        container = ExecutionContainer(tag=image, env=env_vars or {})

        try:
            # Start container
            await container.run()

            # Create execution client
            client = ExecutionClient(container.executor_port)
            await client.connect()

            # Create session
            session = Session(
                session_id=session_id,
                container=container,
                client=client,
                created_at=time.time(),
                last_activity=time.time(),
                timeout=timeout_seconds,
            )

            self.sessions[session_id] = session
            logger.info(f"Created session {session_id}")
            return session

        except Exception:
            # Cleanup on failure
            await container.kill()
            raise

    async def get_session(self, session_id: str) -> Session:
        """Get an existing session or raise error if not found."""
        if session_id not in self.sessions:
            raise ValueError(f"Session {session_id} not found")

        session = self.sessions[session_id]
        session.last_activity = time.time()
        return session

    async def destroy_session(self, session_id: str) -> None:
        """Explicitly destroy a session and cleanup resources."""
        if session_id in self.sessions:
            session = self.sessions[session_id]
            await session.cleanup()
            del self.sessions[session_id]
            logger.info(f"Destroyed session {session_id}")

    async def list_sessions(self) -> List[Session]:
        """Return a list of all active sessions."""
        return list(self.sessions.values())

    async def _cleanup_expired_sessions(self) -> None:
        """Background task to cleanup expired sessions."""
        while True:
            try:
                current_time = time.time()
                expired_sessions = []

                for session_id, session in self.sessions.items():
                    if current_time - session.last_activity > session.timeout:
                        expired_sessions.append(session_id)

                for session_id in expired_sessions:
                    logger.info(f"Session {session_id} expired, cleaning up")
                    await self.destroy_session(session_id)

                await asyncio.sleep(self._cleanup_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in session cleanup: {e}")
                await asyncio.sleep(self._cleanup_interval)


# Global session manager
session_manager = SessionManager()

# Initialize FastMCP server
mcp = FastMCP("ipybox-execution")


@mcp.tool()
async def session_create(
    session_id: str,
    image: str = "gradion-ai/ipybox-test",
    env_vars: Optional[Dict[str, str]] = None,
    timeout_seconds: Optional[int] = None,
    memory_limit: str = "512m",
    cpu_limit: str = "1",
) -> Dict:
    """Create a new isolated execution session with configurable container.

    Args:
        session_id: Unique identifier for the session
        image: Docker image to use for the container
        env_vars: Environment variables to set in the container
        timeout_seconds: Session timeout (defaults to manager's configured timeout)
        memory_limit: Container memory limit (e.g., "512m", "1g") - not implemented yet
        cpu_limit: Container CPU limit (e.g., "1", "0.5") - not implemented yet

    Returns:
        Dict with session info including container_id and status
    """
    session = await session_manager.create_session(
        session_id=session_id,
        image=image,
        env_vars=env_vars,
        timeout_seconds=timeout_seconds,
        memory_limit=memory_limit,
        cpu_limit=cpu_limit,
    )

    return {
        "session_id": session_id,
        "status": "created",
        "executor_port": session.container.executor_port,
        "resource_port": session.container.resource_port,
        "created_at": session.created_at,
    }


@mcp.tool()
async def execute_code(session_id: str, code: str, timeout: float = 120.0) -> Dict:
    """Execute Python code in the specified session.

    Args:
        session_id: Session identifier
        code: Python code to execute
        timeout: Execution timeout in seconds

    Returns:
        Dict with text output, error output, images, and execution status
    """
    try:
        session = await session_manager.get_session(session_id)
        result = await session.execute(code, timeout=timeout)

        # Convert images to base64 for JSON serialization
        images_b64 = []
        for img in result.images:
            import base64
            import io

            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            img_str = base64.b64encode(buffer.getvalue()).decode()
            images_b64.append(img_str)

        return {"text_output": result.text or "", "images": images_b64, "status": "success"}

    except ExecutionError as e:
        return {"text_output": "", "error_output": str(e), "trace": e.trace, "images": [], "status": "error"}
    except asyncio.TimeoutError:
        return {
            "text_output": "",
            "error_output": f"Code execution timed out after {timeout}s",
            "images": [],
            "status": "timeout",
        }


@mcp.tool()
async def upload_file(session_id: str, file_path: str, content: str, encoding: str = "utf-8") -> Dict:
    """Upload a file to the session container filesystem.

    Args:
        session_id: Session identifier
        file_path: Target path in container filesystem
        content: File content as string
        encoding: Text encoding to use

    Returns:
        Dict with file path, size, and status
    """
    session = await session_manager.get_session(session_id)
    content_bytes = content.encode(encoding)
    await session.upload_file(file_path, content_bytes)

    return {"file_path": file_path, "size_bytes": len(content_bytes), "status": "uploaded"}


@mcp.tool()
async def download_file(session_id: str, file_path: str, encoding: str = "utf-8") -> Dict:
    """Download a file from the session container filesystem.

    Args:
        session_id: Session identifier
        file_path: Path to file in container filesystem
        encoding: Text encoding to use for decoding

    Returns:
        Dict with file path, content, size, and status
    """
    session = await session_manager.get_session(session_id)
    content_bytes = await session.download_file(file_path)

    return {
        "file_path": file_path,
        "content": content_bytes.decode(encoding),
        "size_bytes": len(content_bytes),
        "status": "downloaded",
    }


@mcp.tool()
async def list_files(session_id: str, directory_path: str = "/app") -> Dict:
    """List files and directories in the session container.

    Args:
        session_id: Session identifier
        directory_path: Directory path to list

    Returns:
        Dict with directory path, files list, and count
    """
    session = await session_manager.get_session(session_id)

    # For now, use execute_code to list files since we don't have list_files implemented
    # in the resource server yet
    code = f"""
import os
import json
try:
    files = []
    if os.path.exists('{directory_path}'):
        for item in os.listdir('{directory_path}'):
            item_path = os.path.join('{directory_path}', item)
            stat = os.stat(item_path)
            files.append({{
                'name': item,
                'path': item_path,
                'is_directory': os.path.isdir(item_path),
                'size': stat.st_size,
                'modified': stat.st_mtime
            }})
    print(json.dumps(files))
except Exception as e:
    print(json.dumps({{"error": str(e)}}))
"""

    result = await session.execute(code)
    import json

    try:
        files = json.loads(result.text or "[]")
        if isinstance(files, dict) and "error" in files:
            raise ValueError(files["error"])
    except (json.JSONDecodeError, ValueError) as e:
        files = {"error": f"Failed to list directory: {e}"}

    return {"directory": directory_path, "files": files, "count": len(files) if isinstance(files, list) else 0}


@mcp.tool()
async def install_package(session_id: str, package: str, index_url: Optional[str] = None) -> Dict:
    """Install Python packages in the session container.

    Args:
        session_id: Session identifier
        package: Package name to install
        index_url: Optional custom package index URL

    Returns:
        Dict with installation result
    """
    pip_cmd = f"!pip install {package}"
    if index_url:
        pip_cmd += f" -i {index_url}"

    return await execute_code.fn(session_id, pip_cmd)


@mcp.tool()
async def session_status(session_id: str) -> Dict:
    """Get detailed status information about a session.

    Args:
        session_id: Session identifier

    Returns:
        Dict with session status information
    """
    session = await session_manager.get_session(session_id)

    return {
        "session_id": session_id,
        "uptime_seconds": time.time() - session.created_at,
        "last_activity": session.last_activity,
        "timeout": session.timeout,
        "status": "active",
    }


@mcp.tool()
async def session_destroy(session_id: str) -> Dict:
    """Explicitly destroy a session and cleanup all resources.

    Args:
        session_id: Session identifier

    Returns:
        Dict with destruction status
    """
    await session_manager.destroy_session(session_id)

    return {"session_id": session_id, "status": "destroyed"}


@mcp.tool()
async def list_sessions() -> Dict:
    """List all active sessions managed by this server.

    Returns:
        Dict with active sessions information
    """
    sessions = await session_manager.list_sessions()

    return {
        "active_sessions": len(sessions),
        "sessions": [
            {
                "session_id": s.session_id,
                "uptime": time.time() - s.created_at,
                "last_activity": s.last_activity,
                "timeout": s.timeout,
            }
            for s in sessions
        ],
    }


async def setup_server() -> None:
    """Initialize the MCP server and session manager."""
    await session_manager.start()
    logger.info("ipybox MCP server initialized")


async def shutdown_server() -> None:
    """Cleanup server resources."""
    await session_manager.stop()
    logger.info("ipybox MCP server shutdown")


if __name__ == "__main__":
    import uvicorn

    # Configure logging
    logging.basicConfig(level=logging.INFO)

    # Create the HTTP app
    app = mcp.http_app()

    # Setup lifecycle events
    app.add_event_handler("startup", setup_server)
    app.add_event_handler("shutdown", shutdown_server)

    # Run the server
    uvicorn.run(app, host="0.0.0.0", port=8081)
