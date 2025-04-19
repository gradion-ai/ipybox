import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Annotated

import typer

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
            dependencies_spec = f.read()

        with open(pkg_path / "config" / "default" / "pyproject.toml", "r") as f:
            project_spec = f.read()

        with open(tmp_path / "pyproject.toml", "w") as f:
            f.write(project_spec.format(dependencies=dependencies_spec))

        ipybox_path = tmp_path / "ipybox"
        ipybox_path.mkdir()

        if root:
            dockerfile = "Dockerfile.root"
            build_cmd_args = []
        else:
            dockerfile = "Dockerfile"
            build_cmd_args = [
                "--build-arg",
                f"UID={os.getuid()}",
                "--build-arg",
                f"GID={os.getgid()}",
            ]

        shutil.copytree(pkg_path / "mcp", tmp_path / "ipybox" / "mcp")
        shutil.copytree(pkg_path / "resource", tmp_path / "ipybox" / "resource")
        shutil.copy(pkg_path / "modinfo.py", tmp_path / "ipybox")
        shutil.copy(pkg_path / "config" / "default" / "environment.yml", tmp_path)
        shutil.copy(pkg_path / "docker" / dockerfile, tmp_path)
        shutil.copy(pkg_path / "scripts" / "server.sh", tmp_path)

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


if __name__ == "__main__":
    app()
