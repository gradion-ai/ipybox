# MCP server

[ipybox](https://gradion-ai.github.io/ipybox/index.md) is a Python code execution sandbox with first-class support for programmatic MCP tool calling. Code executes in a sandboxed IPython Kernel, providing a stateful environment where variables and definitions persist across executions.

When run as an MCP server, it exposes these capabilities to MCP clients like Claude Code or Claude Desktop. Agents can register MCP servers, then execute Python code that uses them programmatically:

1. Agent calls [`register_mcp_server`](#register_mcp_server) to [generate a typed Python API](https://gradion-ai.github.io/ipybox/apigen/index.md) for the tools of an MCP server
1. Agent calls [`execute_ipython_cell`](#execute_ipython_cell) to [execute Python code](https://gradion-ai.github.io/ipybox/codeexec/index.md) that imports and uses the generated API

Application example

An application example of this MCP server is the [programmatic tool calling plugin](https://gradion-ai.github.io/ipybox/ccplugin/index.md) for Claude Code.

## Configuration

```json
{
  "mcpServers": {
    "ipybox": {
      "command": "uvx",
      "args": [
        "ipybox",
        "--workspace",
        "/path/to/workspace"
      ]
    }
  }
}
```

## Workspace

The `--workspace` option specifies the ipybox working directory, default is `"."`. Generated [Python tool APIs](https://gradion-ai.github.io/ipybox/apigen/index.md) are written to `mcptools/` in the workspace, and [code execution](#execute_ipython_cell) use the workspace as working directory.

## Environment variables

Environment variables can be passed to ipybox either via an `"env"` key in the MCP [configuration](#configuration) or in an `.env` file in the workspace directory:

/path/to/workspace/.env

```text
API_KEY_1=...
API_KEY_2=...
KERNEL_ENV_SECRET_1=...
KERNEL_ENV_SECRET_2=...
```

These variables are available to MCP servers registered with ipybox but are not passed to the IPython kernel by default. To make them available to the kernel, use the `KERNEL_ENV_` prefix. For example, `KERNEL_ENV_SECRET_1` is available as `SECRET_1` in the kernel.

## Usage example

This example shows a typical workflow using the [Brave Search MCP server](https://github.com/modelcontextprotocol/servers/tree/main/src/brave-search). First, configure the ipybox MCP server with a [BRAVE_API_KEY](https://gradion-ai.github.io/ipybox/quickstart/#get-a-brave-api-key):

```json
{
  "mcpServers": {
    "ipybox": {
      "command": "uvx",
      "args": ["ipybox", "--workspace", "/path/to/workspace"],
      "env": {
        "BRAVE_API_KEY": "your-api-key"
      }
    }
  }
}
```

or add the API key to a `.env` file in the workspace directory:

/path/to/workspace/.env

```text
BRAVE_API_KEY=your-api-key
```

An agent then registers the Brave Search MCP server by calling `register_mcp_server` with the following argument:

```json
{
  "server_name": "brave_search",
  "server_params": {
    "command": "npx",
    "args": ["-y", "@anthropic/mcp-server-brave-search"],
    "env": {"BRAVE_API_KEY": "${BRAVE_API_KEY}"}
  }
}
```

The `${BRAVE_API_KEY}` placeholder is replaced with the actual value from the MCP configuration or the `.env` file. ipybox connects to the Brave Search MCP server and generates a Python tool API under `mcptools/brave_search/`.

After registration, the agent calls `execute_ipython_cell` with Python code that uses the generated API:

```python
from mcptools.brave_search.brave_web_search import Params, run

result = run(Params(query="Python asyncio tutorial", count=3))
print(result)
```

The printed result is returned and added to the agent's context window.

## Tools

The ipybox MCP server exposes four tools.

### `register_mcp_server`

Connects to an MCP server and [generates a Python API](https://gradion-ai.github.io/ipybox/apigen/index.md) for its tools under `mcptools/{server_name}/`.

Parameters:

- `server_name` — Application-defined MCP server name (valid Python identifier)
- `server_params` — Server config: `{"command", "args", "env"}` for stdio or `{"url", "headers"}` for HTTP

### `execute_ipython_cell`

Executes Python code in a stateful IPython kernel. Executed code can use the generated Python tool API of [registered MCP servers](#register_mcp_server). MCP tool calls from executed code are [auto-approved](https://gradion-ai.github.io/ipybox/codeexec/#basic-execution).

Parameters:

- `code` — Python code to execute
- `timeout` — Maximum execution time in seconds (default: 120)
- `max_output_chars` — Output character limit (default: 5000)

Returns the execution output.

### `install_package`

Installs a Python package via `pip`. Supports version specifiers and git URLs.

Parameters:

- `package_name` — Package spec (e.g., `requests`, `numpy>=1.20.0`, or `git+https://...`)

### `reset`

Creates a new kernel, clearing all variables and imports. Installed packages and generated `mcptools/` persist.

## Sandboxing

To isolate code execution via Anthropic's [sandbox-runtime](https://github.com/anthropic-experimental/sandbox-runtime), enable [sandboxing](https://gradion-ai.github.io/ipybox/sandbox/index.md) with the `--sandbox` option:

```json
{
  "mcpServers": {
    "ipybox": {
      "command": "uvx",
      "args": [
        "ipybox",
        "--workspace",
        "/path/to/workspace",
        "--sandbox",
        "--sandbox-config",
        "/path/to/sandbox-config.json"
      ]
    }
  }
}
```

The default sandbox configuration permits reading all files except `.env` and writing to the current directory and subdirectories (plus IPython directories). Access to internet is blocked. An optional custom sandbox configuration can be passed with the `--sandbox-config` option.

Info

Sandboxing with [sandbox-runtime](https://github.com/anthropic-experimental/sandbox-runtime) currently works on Mac OS only. On Linux and Windows, you can either run ipybox without sandboxing or as a [Docker container](#docker).

## Docker

ipybox can be run as a Docker container. Clone the [project](https://github.com/gradion-ai/ipybox) and build the image:

```bash
git clone https://github.com/gradion-ai/ipybox.git
cd ipybox
./docker-build.sh
```

The build script creates a container user with your UID/GID, ensuring files generated by ipybox in the mounted workspace are owned by you and can be edited on the host.

Then configure the MCP server:

```json
{
  "mcpServers": {
    "ipybox": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "-v",
        "/path/to/workspace:/app/workspace",
        "ipybox"
      ]
    }
  }
}
```

The workspace `/path/to/workspace` on the host is mounted to `/app/workspace` inside the container.
