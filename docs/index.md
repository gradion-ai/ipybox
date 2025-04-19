# Overview

`ipybox` is a lightweight, stateful and secure Python code execution sandbox built with [IPython](https://ipython.org/) and [Docker](https://www.docker.com/). Designed for AI agents that interact with their environment through code execution, like the [`freeact`](https://gradion-ai.github.io/freeact/) agent system, it is also well-suited for general-purpose code execution. `ipybox` is fully open-source and free to use, distributed under the Apache 2.0 license.

<figure markdown>
  ![logo](img/logo.png){ width="400" style="display: block; margin: 0 auto" }
</figure>

## Features

- **Secure Execution**: Executes code in Docker container locally or remotely
- **Stateful Execution**: Maintains state across code executions using IPython kernels
- **Output Streaming**: Provides immediate feedback through direct output streaming
- **Plotting Support**: Enables downloading of plots created with visualization libraries
- **MCP Support**: Generate Python functions from MCP tools and use them during code execution
- **Dependency Management**: Supports package installation during runtime or at build time
- **Resource Management**: Context manager based container and IPython kernel lifecycle management
- **Reproducible Environments**: Ensures consistent execution environments across different systems
