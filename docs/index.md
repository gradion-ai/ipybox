# Introduction

## Overview

`ipybox` is a lightweight and secure Python code execution sandbox based on [IPython](https://ipython.org/) and [Docker](https://www.docker.com/). You can run it locally on your computer or remotely in an environment of your choice. `ipybox` is designed for AI agents that need to execute code safely e.g. for data analytics use cases or executing code actions like in [`freeact`](https://gradion-ai.github.io/freeact/) agents.

<figure markdown>
  ![logo](img/logo.png){ width="300" style="display: block; margin: 0 auto" }
</figure>

## Features

- Secure code execution inside Docker containers
- [Restrict network access](examples.md#restrict-network-access) with a configurable firewall
- Stateful code execution with IPython kernels
- Stream code execution output as it is generated
- Install Python packages at build time or runtime
- Return plots generated with visualization libraries
- Exposes an [MCP server](mcp-server.md) interface for AI agent integration
- [Invocation of MCP servers](mcp-client.md) via generated client code
- Flexible deployment options, local or remote
- `asyncio` API for managing the execution environment
