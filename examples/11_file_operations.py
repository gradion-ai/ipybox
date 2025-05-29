"""
File upload and download operations with ipybox.

This example demonstrates how to:
- Upload single files to containers
- Upload entire directories
- Download files from containers
- Download directories as archives
- Delete files in containers

Note: Make sure to build the Docker image first:
    python -m ipybox build -t gradion-ai/ipybox
"""

import asyncio
from pathlib import Path

from ipybox import ExecutionClient, ExecutionContainer, ResourceClient


async def main():
    # --8<-- [start:usage]
    input_dir = Path("examples", "data")

    async with ExecutionContainer() as container:
        async with ResourceClient(port=container.resource_port) as res_client:
            async with ExecutionClient(port=container.executor_port) as exec_client:
                await res_client.upload_file("data/example.txt", input_dir / "example.txt")  # (1)!
                await res_client.upload_directory("data/subdir", input_dir / "subdir")  # (2)!

                await exec_client.execute("""
                    import os
                    import shutil
                    os.makedirs('output', exist_ok=True)
                    shutil.copy('data/example.txt', 'output/example.txt')
                    shutil.copytree('data/subdir', 'output/subdir')
                """)  # (3)!

                output_dir = Path("examples", "output")
                output_dir.mkdir(exist_ok=True, parents=True)
                await res_client.download_file("output/example.txt", output_dir / "example.txt")  # (4)!
                await res_client.download_directory("output/subdir", output_dir / "subdir")  # (5)!
                await res_client.delete_file("data/example.txt")  # (6)!
    # --8<-- [end:usage]


if __name__ == "__main__":
    asyncio.run(main())
