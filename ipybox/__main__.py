import asyncio
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Annotated, Optional

import typer
from dotenv import dotenv_values

from ipybox.container import DEFAULT_TAG

pkg_path = Path(__file__).parent
app = typer.Typer()


@app.command()
def build(
    tag: Annotated[
        str,
        typer.Option(
            "--tag",
            "-t",
            help="Name and optionally a tag of the Docker image in 'name:tag' format",
        ),
    ] = DEFAULT_TAG,
    dependencies: Annotated[
        Path,
        typer.Option(
            "--dependencies",
            "-d",
            help="Path to dependencies file",
            exists=True,
            file_okay=True,
            dir_okay=False,
        ),
    ] = Path(__file__).parent / "config" / "default" / "dependencies.txt",
    root: Annotated[
        bool,
        typer.Option(
            "--root",
            "-r",
            help="Run container as root",
        ),
    ] = False,
):
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        with open(dependencies, "r") as f:
            if dependencies_spec := f.read():
                dependencies_spec = dependencies_spec.strip()
                if dependencies_spec:
                    dependencies_spec = f",\n{dependencies_spec}"

        with open(pkg_path / "config" / "default" / "pyproject.toml", "r") as f:
            project_spec = f.read()

        with open(tmp_path / "pyproject.toml", "w") as f:
            f.write(project_spec.format(dependencies=dependencies_spec))

        ipybox_path = tmp_path / "ipybox"
        ipybox_path.mkdir()

        if root:
            dockerfile = "Dockerfile.root"
            firewall_script = "init-firewall-root.sh"
            build_cmd_args = []
        else:
            dockerfile = "Dockerfile"
            firewall_script = "init-firewall.sh"
            build_cmd_args = [
                "--build-arg",
                f"UID={os.getuid()}",
                "--build-arg",
                f"GID={os.getgid()}",
            ]

        shutil.copytree(pkg_path / "mcp", tmp_path / "ipybox" / "mcp")
        shutil.copytree(pkg_path / "resource", tmp_path / "ipybox" / "resource")
        shutil.copy(pkg_path / "config" / "default" / ".python-version", tmp_path)
        shutil.copy(pkg_path / "modinfo.py", tmp_path / "ipybox")
        shutil.copy(pkg_path / "docker" / dockerfile, tmp_path)
        shutil.copy(pkg_path / "scripts" / "server.sh", tmp_path)
        shutil.copy(pkg_path / "docker" / firewall_script, tmp_path)

        build_cmd = [
            "docker",
            "build",
            "-f",
            tmp_path / dockerfile,
            "-t",
            tag,
            str(tmp_path),
            *build_cmd_args,
        ]

        process = subprocess.Popen(build_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)  # type: ignore

        while True:
            output = process.stdout.readline()  # type: ignore
            if output == "" and process.poll() is not None:
                break
            if output:
                print(output.strip())

        if process.returncode != 0:
            raise typer.Exit(code=1)


@app.command()
def cleanup(
    ancestor: Annotated[
        str,
        typer.Option(
            "--ancestor",
            "-a",
            help="Name and optionally a tag of the Docker ancestor image in 'name:tag' format",
        ),
    ] = DEFAULT_TAG,
):
    cleanup_script = pkg_path / "scripts" / "cleanup.sh"
    subprocess.run(["bash", str(cleanup_script), ancestor], capture_output=True, text=True)


@app.command()
def mcp(
    allowed_dirs: Annotated[
        Optional[list[Path]],
        typer.Option(
            "--allowed-dir",
            help="Directory allowed for host filesystem operations",
        ),
    ] = None,
    container_tag: Annotated[
        str,
        typer.Option(
            "--container-tag",
            help="Docker image name and tag for the ipybox container",
        ),
    ] = DEFAULT_TAG,
    container_env_vars: Annotated[
        Optional[list[str]],
        typer.Option(
            "--container-env-var",
            help="Environment variable for container (format: KEY=VALUE)",
        ),
    ] = None,
    container_env_file: Annotated[
        Optional[Path],
        typer.Option(
            "--container-env-file",
            file_okay=True,
            dir_okay=False,
            resolve_path=True,
            help="Path to an environment variables file for container",
        ),
    ] = None,
    container_binds: Annotated[
        Optional[list[str]],
        typer.Option(
            "--container-bind",
            help="Bind mounts for container (format: host_path:container_path)",
        ),
    ] = None,
):
    """Run the ipybox MCP server."""
    from ipybox.mcp.server import MCPServer

    # Default allowed directories if not specified
    if allowed_dirs is None:
        allowed_dirs = [Path.home(), Path("/tmp")]

    env = {}
    binds = {}

    if container_env_file:
        file_env = dotenv_values(container_env_file)
        env.update(file_env)

    if container_env_vars:
        for env_str in container_env_vars:
            if "=" in env_str:
                key, value = env_str.split("=", 1)
                env[key] = value

    if container_binds:
        for bind_str in container_binds:
            if ":" in bind_str:
                host_path, container_path = bind_str.split(":", 1)
                binds[host_path] = container_path

    container_config = {
        "tag": container_tag,
        "env": env,
        "binds": binds,
    }

    async def run_server():
        server = MCPServer(
            allowed_dirs=allowed_dirs,
            container_config=container_config,
        )
        await server.run()

    asyncio.run(run_server())


def main():
    app()


if __name__ == "__main__":
    main()
