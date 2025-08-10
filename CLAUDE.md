# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Dependency Management

To add a dependency to the project, run the following command:

```bash
uv add <dependency>
```

To remove a dependency from the project, run the following command:

```bash
uv remove <dependency>
```

Add optional arguments like `--dev` for development dependencies, for example, as needed.

For syncing dependencies after a manual change of `pyproject.toml`, run the following command:

```bash
uv sync
```

### Running Tests

#### General
- `uv run invoke test` for running all unit and integration tests.
- `uv run invoke test --cov` for running all unit and integration tests and generating a coverage report.

#### Unit Tests
- `uv run invoke ut` for running unit tests.
- `uv run invoke ut --cov` for running unit tests and generating a coverage report.

#### Integration Tests
- `uv run invoke it` for running all integration tests.
- `uv run invoke it --cov` for running all integration tests and generating a coverage report.
- `uv run pytest -xsv tests/integration/test_[name].py` for running a single integration test file.
- `uv run pytest -xsv tests/integration/test_[name].py::[test-name]` for running a single integration test.

All invoke test commands use `-xsv` flags by default for verbose output and stopping on first failure.
Coverage reports are displayed in the terminal and cover the `ipybox` package.

### Code Quality

To run code quality checks (linting, formatting, type checking), run the following command:

```bash
uv run invoke code-check
uv run invoke cc  # alias
```

IMPORTANT: The `code-check` command automatically fixes most issues:
- Auto-fixed: Formatting issues (black, isort, etc.) are corrected automatically
- Manual fix required: Type checking errors (mypy) must be fixed manually by you
- No need to manually reformat code - the command handles it for you

### Documentation

To build the documentation, run the following command:

```bash
uv run invoke build-docs
```

To serve the documentation locally at `http://localhost:8000`, run the following command:

```bash
uv run invoke serve-docs
```

## Common Workflows

IMPORTANT: After making ANY code changes (including simple edits), you MUST:

1. If you created any NEW files (untracked files), add them to git with `git add <new-file>`. This is needed for code quality checks to work. Note: You do NOT need to add files that are already tracked by git (i.e., files you only edited).
2. Run code quality checks with `uv run invoke cc`.
3. Run all unit and integration tests with `uv run invoke test`.

This workflow applies to:
- Adding new features
- Fixing bugs
- Refactoring code
- Making ANY edits to Python files, no matter how small
- Updating configuration values
- Changing imports or dependencies

If you see any errors, fix them and then repeat the process.

## Architecture Overview

ipybox is a secure Python code execution sandbox combining Docker containers with IPython kernels for isolated, stateful code execution. Built for AI agents and secure code execution without requiring API keys.

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

**MCP Package** (`ipybox.mcp`)
- `gen.py`: Generates Python client functions from MCP tool schemas using datamodel-code-generator
- `run.py`: Runtime execution of MCP tools supporting stdio, streamable-http, and SSE transports
- Auto-generates typed Pydantic models for tool parameters
- Seamless integration of local (stdio) and remote (streamable-http/SSE) MCP servers
