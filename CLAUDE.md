### Core Architecture

Container-based isolation with dual-server architecture: Jupyter Kernel Gateway (8888) manages IPython kernels for code execution; Resource Server (8900) handles file operations, module introspection, and MCP tool execution through synthesized Python functions. Fully async with Python's asyncio.

### Key Components

**ExecutionContainer** (`container.py`)
- Docker container lifecycle management with auto-pull and health monitoring
- Dynamic host port allocation for executor and resource services
- Bind mounts for host-container file sharing and environment variable injection
- Network firewall initialization restricting outbound traffic to whitelisted domains/IPs/CIDR ranges

**ExecutionClient** (`executor.py`)
- WebSocket connections to IPython kernels via Jupyter Kernel Gateway
- Stateful code execution with persistent variables/definitions across executions
- Real-time output streaming (text, images, errors) with configurable timeouts
- Kernel health monitoring through periodic heartbeats

**ResourceClient/Server** (`resource/client.py`, `resource/server.py`)
- FastAPI RESTful API for resource management
- Bidirectional file/directory transfers (tar archives for directories)
- Python module source code introspection
- MCP server integration through generated Python client functions

**MCP Client** (`ipybox.mcp`)
- `gen.py`: Generates Python client functions from MCP tool schemas using datamodel-code-generator
- `run.py`: Runtime execution of MCP tools supporting stdio, streamable-http, and SSE transports
- Auto-generates typed Pydantic models for tool parameters
- Seamless integration of local (stdio) and remote (streamable-http/SSE) MCP servers

**MCP Server** (`ipybox.mcp.server`)
- FastMCP-based server exposing ipybox as MCP server for secure code execution
- Provides execute_ipython_cell, upload_file, download_file, and reset tools
- Path validation and whitelisting for secure host filesystem operations
