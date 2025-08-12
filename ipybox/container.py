import asyncio
import logging
from collections import defaultdict
from pathlib import Path

from aiodocker import Docker
from aiodocker.containers import DockerContainer

from ipybox.utils import arun

DEFAULT_TAG = "ghcr.io/gradion-ai/ipybox"

logger = logging.getLogger(__name__)


class ExecutionContainer:
    """Context manager for the lifecycle of a code execution Docker container. A code execution container
    provides:

    - a [Jupyter Kernel Gateway](https://jupyter-kernel-gateway.readthedocs.io/) for stateful code execution
      in [IPython kernels](https://ipython.readthedocs.io/). Clients connect to it via
      [`ExecutionClient`][ipybox.executor.ExecutionClient] on the container's
      [executor host port][ipybox.container.ExecutionContainer.executor_port].
    - a *resource server* for downloading Python module sources and registering MCP servers.
      Clients connect to it via [`ResourceClient`][ipybox.resource.client.ResourceClient] on
      the container's [resource host port][ipybox.container.ExecutionContainer.resource_port].
    - a firewall that can be enabled with [init_firewall][ipybox.container.ExecutionContainer.init_firewall]
      to restrict network access to allowed domains, IPv4 addresses, or CIDR ranges.

    Args:
        tag: Name and optionally tag of the `ipybox` Docker image to use (format: `name:tag`)
        binds: A dictionary mapping host paths to container paths for bind mounts.
            Host paths may be relative or absolute. Container paths must be relative
            and are created as subdirectories of `/app` in the container.
        env: Environment variables to set in the container
        executor_port: Host port for the container's executor port. A random port is allocated if not specified.
        resource_port: Host port for the container's resource port. A random port is allocated if not specified.
        port_allocation_timeout: Maximum time in seconds to wait for port random allocation.
        show_pull_progress: Whether to show progress when pulling the Docker image.
    """

    def __init__(
        self,
        tag: str = DEFAULT_TAG,
        binds: dict[str, str] | None = None,
        env: dict[str, str] | None = None,
        executor_port: int | None = None,
        resource_port: int | None = None,
        port_allocation_timeout: float = 10,
        show_pull_progress: bool = True,
    ):
        self.tag = tag
        self.binds = binds or {}
        self.env = env or {}
        self.show_pull_progress = show_pull_progress

        self._docker = None
        self._container = None
        self._executor_port = executor_port
        self._resource_port = resource_port
        self._port_allocation_timeout = port_allocation_timeout

    async def __aenter__(self):
        try:
            await self.run()
        except Exception as e:
            await self.kill()
            raise e
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.kill()

    @property
    def executor_port(self) -> int:
        """The host port of the container's executor port. Either an application-defined
        `executor_port` via the constructor or a dynamically allocated random port.

        Raises:
            RuntimeError: If the container is not running and an application-defined
                port was not provided.
        """
        if self._executor_port is None:
            raise RuntimeError("Container not running")
        return self._executor_port

    @property
    def resource_port(self) -> int:
        """The host port of the container's resource port. Either an application-defined
        `resource_port` via the constructor or a dynamically allocated random port.

        Raises:
            RuntimeError: If the container is not running and an application-defined
                port was not provided.
        """
        if self._resource_port is None:
            raise RuntimeError("Container not running")
        return self._resource_port

    async def kill(self):
        """Kills and removes the current code execution Docker container."""
        if self._container:
            await self._container.kill()

        if self._docker:
            await self._docker.close()

    async def init_firewall(self, allowed_domains: list[str] | None = None) -> None:
        """Initialize firewall rules to restrict internet access to a whitelist of
        allowed domains, IPv4 addresses, or CIDR ranges.

        Traffic policy inside the container after initialisation:

        - DNS resolution (UDP/53) is always permitted so that the script itself can resolve
          domains and regular runtime code can still perform look-ups.
        - SSH (TCP/22) is permitted for interaction with the host.
        - Loopback traffic is unrestricted.
        - The host network (\\*/24 derived from the default gateway) is allowed bidirectionally.
        - Bidirectional traffic on the ipybox *executor* (8888) and *resource* (8900) ports
          is always allowed.
        - Outbound traffic is allowed only to the specified whitelist entries.

        DNS failures when resolving an allowed domain yield a warning but do not stop
        the firewall initialization.

        A firewall can be initialized multiple times per container. Subsequent calls will
        clear previous firewall rules and enforce the new `allowed_domains` list.

        Args:
            allowed_domains: List of domains, IP addresses, or CIDR ranges that should be
                reachable from the container. If None or empty, only essential services are
                allowed.

        Raises:
            RuntimeError: If the container is not running, firewall initialization fails,
                or if the container is running as root (ipybox images built with -r flag).
        """
        if not self._container:
            raise RuntimeError("Container not running")

        if allowed_domains is None:
            allowed_domains = []

        # Build command arguments
        cmd_args = ["/usr/local/bin/init-firewall.sh"]
        cmd_args.extend(allowed_domains)
        cmd_args.extend(["--executor-port", str(8888), "--resource-port", str(8900)])

        try:
            # Execute firewall initialization script as root
            exec_instance = await self._container.exec(
                cmd=cmd_args,
                stdout=True,
                stderr=True,
                tty=False,
                user="root",
            )

            output_chunks: list[bytes] = []
            async with exec_instance.start(detach=False) as stream:
                while True:
                    msg = await stream.read_out()
                    if msg is None:
                        break

                    # Append both stdout (stream==1) and stderr (stream==2)
                    # data so we don't lose any diagnostic information.
                    if msg.data:
                        output_chunks.append(msg.data)

            output_text = b"".join(output_chunks).decode(errors="replace")

            # Check the exit status to ensure the firewall script completed successfully.
            # If the script fails, raise an error with the exit code and the output text.
            inspect_data = await exec_instance.inspect()
            exit_code = inspect_data.get("ExitCode")

            if exit_code not in (0, None):
                error_message = f"init script returned exit code {exit_code}."
                error_message = error_message + f"\n{output_text}" if output_text else ""
                raise RuntimeError(error_message)
            else:
                for line in output_text.splitlines():
                    logger.info(line)

        except Exception as e:
            raise RuntimeError(f"Failed to initialize firewall: {str(e)}") from e

    async def run(self):
        """Creates and starts a code execution Docker container."""
        self._docker = Docker()
        await self._run()

    async def _run(self):
        executor_host_port = {"HostPort": str(self._executor_port)} if self._executor_port else {}
        resource_host_port = {"HostPort": str(self._resource_port)} if self._resource_port else {}

        executor_port_key = f"{8888}/tcp"
        resource_port_key = f"{8900}/tcp"

        config = {
            "Image": self.tag,
            "HostConfig": {
                "CapAdd": [
                    "NET_ADMIN",
                    "NET_RAW",
                ],
                "PortBindings": {
                    executor_port_key: [executor_host_port],
                    resource_port_key: [resource_host_port],
                },
                "AutoRemove": True,
                "Binds": await self._container_binds(),
            },
            "Env": self._container_env(),
            "ExposedPorts": {
                executor_port_key: {},
                resource_port_key: {},
            },
        }

        if not await self._local_image():
            await self._pull_image()

        container = await self._docker.containers.create(config=config)  # type: ignore
        await container.start()

        self._container = container
        self._executor_port = await self._host_port(container, executor_port_key)
        self._resource_port = await self._host_port(container, resource_port_key)

        return container

    async def _host_port(self, container: DockerContainer, executor_port_key: str) -> int:
        try:
            async with asyncio.timeout(self._port_allocation_timeout):
                while True:
                    container_info = await container.show()
                    host_ports = container_info["NetworkSettings"]["Ports"].get(executor_port_key)
                    if host_ports and host_ports[0].get("HostPort"):
                        return int(host_ports[0]["HostPort"])
                    await asyncio.sleep(0.1)

        except TimeoutError:
            raise TimeoutError(
                f"Timed out waiting for host port allocation after {self._port_allocation_timeout} seconds"
            )

    async def _local_image(self) -> bool:
        tag = self.tag if ":" in self.tag else f"{self.tag}:latest"

        images = await self._docker.images.list()  # type: ignore
        for img in images:
            if "RepoTags" in img and img["RepoTags"] is not None and tag in img["RepoTags"]:
                return True

        return False

    async def _pull_image(self):
        # Track progress by layer ID
        layer_progress = defaultdict(str)

        async for message in self._docker.images.pull(self.tag, stream=True):  # type: ignore
            if not self.show_pull_progress:
                continue

            if "status" in message:
                status = message["status"]
                if "id" in message:
                    layer_id = message["id"]
                    if "progress" in message:
                        layer_progress[layer_id] = f"{status}: {message['progress']}"
                    else:
                        layer_progress[layer_id] = status

                    # Clear screen and move cursor to top
                    print("\033[2J\033[H", end="")
                    # Print all layer progress
                    for layer_id, progress in layer_progress.items():
                        print(f"{layer_id}: {progress}")
                else:
                    # Status without layer ID (like "Downloading" or "Complete")
                    print(f"\r{status}", end="")

        if self.show_pull_progress:
            print()

    async def _container_binds(self) -> list[str]:
        container_binds = []
        for host_path, container_path in self.binds.items():
            host_path_resolved = await arun(self._prepare_host_path, host_path)
            container_binds.append(f"{host_path_resolved}:/app/{container_path}")
        return container_binds

    def _prepare_host_path(self, host_path: str) -> Path:
        resolved = Path(host_path).resolve()
        if not resolved.exists():
            resolved.mkdir(parents=True)
        return resolved

    def _container_env(self) -> list[str]:
        return [f"{k}={v}" for k, v in self.env.items()]
