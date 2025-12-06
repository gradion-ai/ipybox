# Quickstart

This guide walks through a complete example: generating a Python tool API for the [Brave Search MCP server](https://github.com/brave/brave-search-mcp-server), executing code that calls it, and handling tool call approvals.

## Installation

```bash
pip install ipybox
```

## Get a Brave API key

Sign up for a free API key at [api.search.brave.com](https://api.search.brave.com). Once you have your key, set it as an environment variable:

```bash
export BRAVE_API_KEY=your_api_key_here
```

Or create a `.env` file in your project root (ipybox loads it automatically):

```env
BRAVE_API_KEY=your_api_key_here
```

## Complete example

```python
--8<-- "examples/quickstart.py"
```

## How it works

### Server parameters

The `server_params` dict defines how to connect to an MCP server. For stdio servers (local processes), you specify:

- `command`: The executable to run
- `args`: Command-line arguments
- `env`: Environment variables to pass

```python
SERVER_PARAMS = {
    "command": "npx",
    "args": ["-y", "@brave/brave-search-mcp-server", "--transport", "stdio"],
    "env": {"BRAVE_API_KEY": "${BRAVE_API_KEY}"},
}
```

The `${BRAVE_API_KEY}` placeholder is replaced with the actual value from your environment when ipybox starts the MCP server.

### Generating a Python tool API

`generate_mcp_sources()` connects to the MCP server, discovers its tools, and generates typed Python modules from their schema:

```python
await generate_mcp_sources(
    server_name="brave_search",
    server_params=SERVER_PARAMS,
    root_dir=Path("mcptools"),
)
```

This creates a package structure like:

```
mcptools/brave_search/
├── __init__.py
├── brave_web_search.py
├── brave_local_search.py
├── brave_image_search.py
└── ...
```

Each module contains a Pydantic `Params` class for input validation, a `Result` class or `str` return type, and a `run()` function that executes the MCP tool.

### Code execution

`CodeExecutor` runs Python code in an IPython kernel. Variables and definitions persist across executions, enabling stateful workflows.

```python
async with CodeExecutor() as executor:
    async for item in executor.stream(CODE):
        ...
```

The `stream()` method yields events as execution progresses. You'll receive `ApprovalRequest` events when the code calls an MCP tool, and a final `CodeExecutionResult` with the output.

### Tool call approval

When executed code calls the generated Python tool API, ipybox pauses execution and sends an `ApprovalRequest` to your application. You must explicitly approve or reject each tool call:

```python
case ApprovalRequest() as req:
    if user_approves:
        await req.accept()
    else:
        await req.reject()
```

The `ApprovalRequest` includes the server name, tool name, and arguments, so you can make informed decisions or implement custom approval logic.

## Next steps

- [API Generation](apigen.md) - Generating typed Python APIs from MCP tools
- [Code Execution](codeexec.md) - Running code and handling tool approvals
- [Sandboxing](sandbox.md) - Secure execution with network and filesystem isolation
