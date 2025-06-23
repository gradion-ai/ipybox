# Introduction

## Overview

`ipybox` is a lightweight and secure Python code execution sandbox based on [IPython](https://ipython.org/) and [Docker](https://www.docker.com/). You can run it locally on your computer or remotely in an environment of your choice - no API key required.

Designed for AI agents that interact with their environment through code execution, like [`freeact`](https://gradion-ai.github.io/freeact/) agents, it is also well-suited for many other secure code execution use cases. `ipybox` is fully open-source and distributed under the Apache 2.0 license.

<figure markdown>
  ![logo](img/logo.png){ width="300" style="display: block; margin: 0 auto" }
</figure>

## Features

- Secure code execution inside Docker containers
- [Restrict network access](usage.md#restrict-network-access) with a configurable firewall
- Stateful code execution with IPython kernels
- Stream code execution output as it is generated
- Install Python packages at build time or runtime
- Return plots generated with visualization libraries
- [Invocation of MCP servers](usage.md#mcp-integration) via generated client code
- Flexible deployment options, local or remote
- `asyncio` API for managing the execution environment
