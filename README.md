# ipybox

<p align="left">
    <a href="https://gradion-ai.github.io/ipybox/"><img alt="Website" src="https://img.shields.io/website?url=https%3A%2F%2Fgradion-ai.github.io%2Fipybox%2F&up_message=online&down_message=offline&label=docs"></a>
    <a href="https://pypi.org/project/ipybox/"><img alt="PyPI - Version" src="https://img.shields.io/pypi/v/ipybox?color=blue"></a>
    <a href="https://github.com/gradion-ai/ipybox/releases"><img alt="GitHub Release" src="https://img.shields.io/github/v/release/gradion-ai/ipybox"></a>
    <a href="https://github.com/gradion-ai/ipybox/actions"><img alt="GitHub Actions Workflow Status" src="https://img.shields.io/github/actions/workflow/status/gradion-ai/ipybox/test.yml"></a>
    <a href="https://github.com/gradion-ai/ipybox/blob/main/LICENSE"><img alt="GitHub License" src="https://img.shields.io/github/license/gradion-ai/ipybox?color=blueviolet"></a>
    <a href="https://pypi.org/project/ipybox/"><img alt="PyPI - Python Version" src="https://img.shields.io/pypi/pyversions/ipybox"></a>
</p>

`ipybox` is a lightweight, stateful and secure Python code execution sandbox built with [IPython](https://ipython.org/) and [Docker](https://www.docker.com/). Designed for AI agents that interact with their environment through code execution, like the [`freeact`](https://github.com/gradion-ai/freeact/) agent system, it is also well-suited for general-purpose code execution. `ipybox` is fully open-source and free to use, distributed under the Apache 2.0 license.

<p align="center">
  <img src="docs/img/logo.png" alt="logo">
</p>

## Features

- **Secure Execution**: Executes code in Docker container locally or remotely
- **Stateful Execution**: Maintains state across code executions using IPython kernels
- **Output Streaming**: Provides immediate feedback through direct output streaming
- **Plotting Support**: Enables downloading of plots created with visualization libraries
- **MCP Support**: Generate Python functions from MCP tools and use them during code execution
- **Dependency Management**: Supports package installation during runtime or at build time
- **Resource Management**: Context manager based container and IPython kernel lifecycle management
- **Reproducible Environments**: Ensures consistent execution environments across different systems

Find out more in the [user guide](https://gradion-ai.github.io/ipybox/).

## Quickstart

Install `ipybox` Python package:

```bash
pip install ipybox
```

Execute Python code inside `ipybox`:

```python
import asyncio
from ipybox import ExecutionClient, ExecutionContainer

async def main():
    async with ExecutionContainer(tag="ghcr.io/gradion-ai/ipybox:minimal") as container:
        async with ExecutionClient(port=container.executor_port) as client:
            result = await client.execute("print('Hello, world!')")
            print(f"Output: {result.text}")

if __name__ == "__main__":
    asyncio.run(main())
```

## MCP Support

`ipybox` also supports the generation of Python functions from MCP tools. When called, they execute the corresponding tools on the MCP server.

```python
import asyncio

from ipybox import ExecutionClient, ExecutionContainer, ResourceClient


async def main():
    server_params = {
        "command": "uvx",
        "args": ["mcp-server-fetch"],
    }

    async with ExecutionContainer(tag="ghcr.io/gradion-ai/ipybox:minimal") as container:
        async with ResourceClient(port=container.resource_port) as client:
            # generate Python functions from MCP server metadata
            generate_result = await client.generate_mcp_sources(
                relpath="mcpgen",
                server_name="fetchurl",
                server_params=server_params,
            )
            # tool names provided by MCP server
            assert generate_result == ["fetch"]

            # retrieve generated sources if needed
            generated_sources = await client.get_mcp_sources(
                relpath="mcpgen",
                server_name="fetchurl",
            )
            assert "def fetch(params: Params) -> str:" in generated_sources["fetch"]

        async with ExecutionClient(port=container.executor_port) as client:
            # call the generated function in the container
            result = await client.execute("""
                from mcpgen.fetchurl.fetch import Params, fetch
                print(fetch(Params(url="https://www.gradion.ai")))
            """)
            print(result.text[:375])


if __name__ == "__main__":
    asyncio.run(main())
```

The script executes the [generated `fetch` function](docs/mcpgen/fetchurl/) in the `ipybox` container and then prints the first 375 characters of the fetched content:

````
Contents of https://www.gradion.ai/:
```

                         ___                    _
   ____ __________ _____/ (_)___  ____   ____ _(_)
  / __ `/ ___/ __ `/ __  / / __ \/ __ \ / __ `/ /
 / /_/ / /  / /_/ / /_/ / / /_/ / / / // /_/ / /
 \__, /_/   \__,_/\__,_/_/\____/_/ /_(_)__,_/_/
/____/
```
````
