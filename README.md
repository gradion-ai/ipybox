# ipybox

<p align="left">
    <a href="https://gradion-ai.github.io/ipybox/"><img alt="Website" src="https://img.shields.io/website?url=https%3A%2F%2Fgradion-ai.github.io%2Fipybox%2F&up_message=online&down_message=offline&label=docs"></a>
    <a href="https://pypi.org/project/ipybox/"><img alt="PyPI - Version" src="https://img.shields.io/pypi/v/ipybox?color=blue"></a>
    <a href="https://github.com/gradion-ai/ipybox/releases"><img alt="GitHub Release" src="https://img.shields.io/github/v/release/gradion-ai/ipybox"></a>
    <a href="https://github.com/gradion-ai/ipybox/actions"><img alt="GitHub Actions Workflow Status" src="https://img.shields.io/github/actions/workflow/status/gradion-ai/ipybox/test.yml"></a>
    <a href="https://github.com/gradion-ai/ipybox/blob/main/LICENSE"><img alt="GitHub License" src="https://img.shields.io/github/license/gradion-ai/ipybox?color=blueviolet"></a>
    <a href="https://pypi.org/project/ipybox/"><img alt="PyPI - Python Version" src="https://img.shields.io/pypi/pyversions/ipybox"></a>
</p>

`ipybox` is a lightweight and secure Python code execution sandbox based on [IPython](https://ipython.org/) and [Docker](https://www.docker.com/). You can run it locally on your computer or remotely in an environment of your choice - no API key required.

Designed for AI agents that interact with their environment through code execution, like [`freeact`](https://github.com/gradion-ai/freeact/) agents, it is also well-suited for many other secure code execution use cases. `ipybox` is fully open-source and distributed under the Apache 2.0 license.

<p align="center">
  <img src="docs/img/logo.png" alt="logo">
</p>

## Features

- Secure code execution inside Docker containers
- [Restrict network access](https://gradion-ai.github.io/ipybox/usage/#restrict-network-access) with a configurable firewall
- Stateful code execution with IPython kernels
- Stream code execution output as it is generated
- Install Python packages at build time or runtime
- Return plots generated with visualization libraries
- [Invocation of MCP servers](https://gradion-ai.github.io/ipybox/usage/#mcp-integration) via generated client code
- Flexible deployment options, local or remote
- `asyncio` API for managing the execution environment

## Documentation

- [User Guide](https://gradion-ai.github.io/ipybox/)
- [API Docs](https://gradion-ai.github.io/ipybox/api/execution_container/)

## Quickstart

Install `ipybox` Python package:

```bash
pip install ipybox
```

Execute Python code in an `ipybox` container:

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
