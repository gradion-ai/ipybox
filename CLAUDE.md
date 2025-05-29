# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Setup

- @.cursor/rules/project-setup.mdc

### Common Commands

- @.cursor/rules/running-tests.mdc
- @.cursor/rules/project-dependencies.mdc

Additional commands are:

```bash
# Code quality checks (linting, formatting, type checking)
invoke code-check
invoke cc  # alias

# Documentation
invoke build-docs    # Build docs
invoke deploy-docs   # Deploy to GitHub Pages
```

## Architecture Overview

ipybox is a secure Python code execution sandbox that combines Docker containers with IPython kernels to provide isolated, stateful code execution. Designed for AI agents and secure code execution use cases, it operates without requiring API keys and can run locally or remotely.

### Core Architecture

The system employs a container-based isolation model with a two-server architecture. Inside each Docker container, a Jupyter Kernel Gateway (port 8888) manages IPython kernel sessions for code execution, while a Resource Server (port 8900) handles file operations and MCP integration. The entire architecture is built on Python's asyncio for efficient concurrent operations.

### Key Components

**ExecutionContainer** (`container.py`)
- Manages the complete Docker container lifecycle from creation to cleanup
- Handles dynamic host port allocation for both executor (8888) and resource (8900) services
- Supports bind mounts for host-container file sharing and environment variable injection
- Auto-pulls Docker images with progress tracking and implements health monitoring via port availability checks

**ExecutionClient** (`executor.py`)
- Establishes WebSocket connections to IPython kernels through the Jupyter Kernel Gateway
- Provides stateful code execution where definitions, variables and imports persist across executions
- Implements real-time output streaming with support for text, images, and error handling
- Maintains kernel health through periodic heartbeat pings and handles execution timeouts

**ResourceClient/Server** (`resource/client.py`, `resource/server.py`)
- FastAPI-based server providing RESTful endpoints for resource management
- Enables bidirectional file and directory transfers using tar archives for directories
- Provides Python module introspection to retrieve source code of installed packages
- Integrates with MCP servers through generation and storage of Python client functions for tool execution

### Design Patterns

The architecture emphasizes clean separation of concerns with execution and resource management as distinct services. All major components use context managers to ensure proper resource cleanup. The client-server pattern with well-defined APIs enables flexibility in deployment scenarios. The streaming architecture allows real-time consumption of execution output, critical for long-running operations. Async/await patterns throughout enable efficient handling of concurrent operations.

### MCP Integration

The MCP (Model Context Protocol) integration dynamically generates Python client functions from MCP server tool metadata. It supports both stdio-based servers (running inside containers) and SSE-based servers (external). The system uses datamodel-code-generator to create type-safe Pydantic models for tool parameters, ensuring robust input validation. Generated functions are stored as Python modules that can be imported and executed within the sandbox environment.

### Security & Deployment

Security is achieved through Docker container isolation with each execution environment completely separated. Containers can run in two modes: non-root (default) using the standard Dockerfile with matching host user/group IDs for seamless file operations, or root mode using Dockerfile.root when built with the `--root` flag. The default non-root mode creates an `appuser` with UID/GID matching the building user, enhancing security and file permission compatibility. The architecture supports flexible deployment options from local Docker installations to remote Docker hosts. The system requires no external dependencies or API keys, making it suitable for air-gapped environments. All communication happens over standard HTTP/WebSocket protocols enabling easy integration with existing infrastructure.
