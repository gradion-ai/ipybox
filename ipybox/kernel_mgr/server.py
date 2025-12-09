import argparse
import asyncio
import os
import sys
from pathlib import Path

import psutil


class KernelGateway:
    """Manages a Jupyter Kernel Gateway process.

    The kernel gateway provides a REST and WebSocket API for creating and
    communicating with IPython kernels. Use
    [`KernelClient`][ipybox.kernel_mgr.client.KernelClient] to create and
    connect to an IPython kernel and execute code.

    When sandboxing is enabled, the gateway runs inside Anthropic's
    [sandbox-runtime](https://github.com/anthropic-experimental/sandbox-runtime),
    providing secure isolation for code execution.

    Example:
        ```python
        async with KernelGateway(host="localhost", port=8888) as gateway:
            # Gateway is running, connect with KernelClient
            await gateway.join()  # Wait until gateway stops
        ```
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 8888,
        sandbox: bool = False,
        sandbox_config: Path | None = None,
        log_level: str = "INFO",
        log_to_stderr: bool = False,
        env: dict[str, str] | None = None,
    ):
        """
        Args:
            host: Hostname or IP address to bind the gateway to.
            port: Port number the gateway listens on.
            sandbox: Whether to run the gateway inside the sandbox-runtime.
            sandbox_config: Path to a JSON file with sandbox configuration.
                See the Configuration section of the
                [sandbox-runtime](https://github.com/anthropic-experimental/sandbox-runtime)
                README for available options.
            log_level: Logging level for the gateway process.
            log_to_stderr: Whether to redirect gateway logs to stderr.
            env: Environment variables to set for kernels created by the gateway.
                Kernels do not inherit environment variables from the parent
                process, so any required variables must be explicitly provided.
        """
        self.host = host
        self.port = port

        self.sandbox = sandbox
        self.sandbox_config = sandbox_config

        self.log_level = log_level
        self.log_to_stderr = log_to_stderr
        self.env = env or {}

        self._process: asyncio.subprocess.Process | None = None

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.stop()

    async def start(self):
        """Starts the kernel gateway process.

        Raises:
            RuntimeError: If the gateway is already running.
        """
        if self._process is not None:
            raise RuntimeError("Kernel gateway is already running")

        jupyter_path = Path(sys.prefix) / "bin" / "jupyter"
        log_level = "WARN" if self.log_level == "WARNING" else self.log_level

        cmd = [
            str(jupyter_path),
            "kernelgateway",
            f"--KernelGatewayApp.ip={self.host}",
            f"--KernelGatewayApp.port={self.port}",
            f"--KernelGatewayApp.log_level={log_level}",
            "--KernelGatewayApp.port_retries=0",
            "--KernelGatewayApp.answer_yes=True",
        ]

        if self.sandbox:
            settings_path = self.sandbox_config or Path(__file__).parent / "sandbox.json"
            cmd = ["srt", "--settings", str(settings_path)] + cmd

        process_env = {"PATH": os.environ.get("PATH", "")}
        process_env.update(self.env)

        self._process = await asyncio.create_subprocess_exec(
            *cmd,
            env=process_env,
            stdout=sys.stderr if self.log_to_stderr else None,
        )

    async def stop(self, timeout: float = 10):
        """Stops the kernel gateway process.

        Terminates the gateway and all child processes. If the process doesn't
        stop within the timeout, it is forcefully killed.

        Args:
            timeout: Maximum time in seconds to wait for graceful termination.
        """
        if self._process is None:
            return

        if self._process.returncode is None:
            try:
                parent = psutil.Process(self._process.pid)
                children = parent.children(recursive=True)
            except psutil.NoSuchProcess:
                children = []

            for child in children:
                try:
                    child.terminate()
                except psutil.NoSuchProcess:
                    pass

            self._process.terminate()

            try:
                await asyncio.wait_for(self.join(), timeout=timeout)
            except asyncio.TimeoutError:
                self._process.kill()
                await self.join()

        self._process = None

    async def join(self):
        """Waits for the kernel gateway process to exit."""
        if self._process is None:
            return

        try:
            await self._process.wait()
        except asyncio.CancelledError:
            pass


async def main():
    parser = argparse.ArgumentParser(
        description="Start a Jupyter Kernel Gateway",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--host",
        type=str,
        default="localhost",
        help="The hostname to bind the gateway to",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8888,
        help="The port to bind the gateway to",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="The logging level for the gateway",
    )
    args = parser.parse_args()

    async with KernelGateway(
        host=args.host,
        port=args.port,
        log_level=args.log_level,
    ) as gateway:
        await gateway.join()


if __name__ == "__main__":
    asyncio.run(main())
