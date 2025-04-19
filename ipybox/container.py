import asyncio
from collections import defaultdict
from pathlib import Path

from aiodocker import Docker
from aiodocker.containers import DockerContainer

from ipybox.utils import arun

DEFAULT_TAG = "gradion-ai/ipybox"


class ExecutionContainer:
    """
    A context manager for managing the lifecycle of a Docker container used for code execution.

    It handles the creation, port mapping, volume binding, and cleanup of the container.

    Args:
        tag: Tag of the Docker image to use (defaults to gradion-ai/ipybox)
        binds: Mapping of host paths to container paths for volume mounting.
            Host paths may be relative or absolute. Container paths must be relative
            and are created as subdirectories of `/app` in the container.
        env: Environment variables to set in the container
        executor_port: Host port for the container's executor port. If not provided,
            a random port will be allocated.
        resource_port: Host port for the container's resource port. If not provided,
            a random port will be allocated.
        port_allocation_timeout: Timeout in seconds waiting for the container's host
            port to be allocated. This is only relevant on OSX when `port=None`.
        show_pull_progress: Whether to show progress when pulling the Docker image.

    Example:
        ```python
        from ipybox import ExecutionClient, ExecutionContainer

        binds = {"/host/path": "example/path"}
        env = {"API_KEY": "secret"}

        async with ExecutionContainer(binds=binds, env=env) as container:
            async with ExecutionClient(host="localhost", port=container.executor_port) as client:
                result = await client.execute("print('Hello, world!')")
                print(result.text)
        ```
        > Hello, world!
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
        """
        The host port for the container's executor port.

        This port is dynamically allocated when the container is started unless
        explicitly provided.

        Raises:
            RuntimeError: If the container is not running
        """
        if self._executor_port is None:
            raise RuntimeError("Container not running")
        return self._executor_port

    @property
    def resource_port(self) -> int:
        """
        The host port for the container's resource port.

        This port is dynamically allocated when the container is started unless
        explicitly provided.

        Raises:
            RuntimeError: If the container is not running
        """
        if self._resource_port is None:
            raise RuntimeError("Container not running")
        return self._resource_port

    async def kill(self):
        """
        Kill and remove the Docker container.
        """
        if self._container:
            await self._container.kill()

        if self._docker:
            await self._docker.close()

    async def run(self):
        """
        Create and start the Docker container.
        """
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
