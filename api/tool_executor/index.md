## ipybox.tool_exec.server.ToolServer

```
ToolServer(
    host="localhost",
    port: int = 8900,
    approval_required: bool = False,
    approval_timeout: float | None = None,
    connect_timeout: float = 30,
    log_to_stderr: bool = False,
    log_level: str = "INFO",
)
```

HTTP server that manages MCP servers and executes their tools with optional approval.

ToolServer provides HTTP endpoints for executing MCP tools and a WebSocket endpoint for sending approval requests to clients. MCP servers are started on demand when tools are first executed and cached for subsequent calls.

Endpoints:

- `PUT /reset`: Closes all started MCP servers
- `POST /run`: Executes an MCP tool (with optional approval)
- `WS /approval`: WebSocket endpoint for ApprovalClient connections

Example

```
async with ToolServer(approval_required=True) as server:
    async with ApprovalClient(callback=on_approval_request):
        # Execute code that calls MCP tools
        ...
```

Parameters:

| Name                | Type    | Description                                            | Default                                                                   |
| ------------------- | ------- | ------------------------------------------------------ | ------------------------------------------------------------------------- |
| `host`              |         | Hostname the server binds to.                          | `'localhost'`                                                             |
| `port`              | `int`   | Port number the server listens on.                     | `8900`                                                                    |
| `approval_required` | `bool`  | Whether tool calls require approval.                   | `False`                                                                   |
| `approval_timeout`  | \`float | None\`                                                 | Timeout in seconds for approval requests. If None, no timeout is applied. |
| `connect_timeout`   | `float` | Timeout in seconds for starting MCP servers.           | `30`                                                                      |
| `log_to_stderr`     | `bool`  | Whether to log to stderr instead of stdout.            | `False`                                                                   |
| `log_level`         | `str`   | Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL). | `'INFO'`                                                                  |

### join

```
join()
```

Wait for the HTTP server task to stop.

### start

```
start()
```

Start the HTTP server.

Raises:

| Type           | Description                       |
| -------------- | --------------------------------- |
| `RuntimeError` | If the server is already running. |

### stop

```
stop()
```

Stop the HTTP server and close all managed MCP servers.

## ipybox.tool_exec.client.ToolRunner

```
ToolRunner(
    server_name: str,
    server_params: dict[str, Any],
    host: str = "localhost",
    port: int = 8900,
)
```

Client for executing MCP tools on a ToolServer.

Example

```
runner = ToolRunner(
    server_name="fetch",
    server_params={"command": "uvx", "args": ["mcp-server-fetch"]},
)
result = await runner.run("fetch", {"url": "https://example.com"})
```

Parameters:

| Name            | Type             | Description                    | Default       |
| --------------- | ---------------- | ------------------------------ | ------------- |
| `server_name`   | `str`            | Name of the MCP server.        | *required*    |
| `server_params` | `dict[str, Any]` | MCP server parameters.         | *required*    |
| `host`          | `str`            | Hostname of the ToolServer.    | `'localhost'` |
| `port`          | `int`            | Port number of the ToolServer. | `8900`        |

### reset

```
reset()
```

Reset the `ToolServer`, stopping all started MCP servers.

### run

```
run(
    tool_name: str, tool_args: dict[str, Any]
) -> dict[str, Any] | str | None
```

Execute a tool on the configured MCP server.

Parameters:

| Name        | Type             | Description                    | Default    |
| ----------- | ---------------- | ------------------------------ | ---------- |
| `tool_name` | `str`            | Name of the tool to execute.   | *required* |
| `tool_args` | `dict[str, Any]` | Arguments to pass to the tool. | *required* |

Returns:

| Type             | Description |
| ---------------- | ----------- |
| \`dict[str, Any] | str         |

Raises:

| Type              | Description                                    |
| ----------------- | ---------------------------------------------- |
| `ToolRunnerError` | If tool execution fails or approval is denied. |

### run_sync

```
run_sync(
    tool_name: str, tool_args: dict[str, Any]
) -> dict[str, Any] | str | None
```

Synchronous version of run.

Parameters:

| Name        | Type             | Description                    | Default    |
| ----------- | ---------------- | ------------------------------ | ---------- |
| `tool_name` | `str`            | Name of the tool to execute.   | *required* |
| `tool_args` | `dict[str, Any]` | Arguments to pass to the tool. | *required* |

Returns:

| Type             | Description |
| ---------------- | ----------- |
| \`dict[str, Any] | str         |

Raises:

| Type              | Description                                    |
| ----------------- | ---------------------------------------------- |
| `ToolRunnerError` | If tool execution fails or approval is denied. |

## ipybox.tool_exec.client.ToolRunnerError

Bases: `Exception`

Raised when tool execution fails on the server or when approval is rejected.

## ipybox.tool_exec.approval.client.ApprovalClient

```
ApprovalClient(
    callback: ApprovalCallback,
    host: str = "localhost",
    port: int = 8900,
)
```

Client for handling tool call approval requests.

`ApprovalClient` connects to a ToolServer's ApprovalChannel and receives approval requests. Each request is passed to the registered callback, which must accept or reject the request.

Example

```
async def on_approval_request(request: ApprovalRequest):
    print(f"Approval request: {request}")
    await request.accept()

async with ApprovalClient(callback=on_approval_request):
    # Execute code that triggers MCP tool calls
    ...
```

Parameters:

| Name       | Type               | Description                                      | Default       |
| ---------- | ------------------ | ------------------------------------------------ | ------------- |
| `callback` | `ApprovalCallback` | Async function called for each approval request. | *required*    |
| `host`     | `str`              | Hostname of the ToolServer.                      | `'localhost'` |
| `port`     | `int`              | Port number of the ToolServer.                   | `8900`        |

### connect

```
connect()
```

Connect to a `ToolServer`'s `ApprovalChannel`.

### disconnect

```
disconnect()
```

Disconnect from the `ToolServer`'s `ApprovalChannel`.

## ipybox.tool_exec.approval.client.ApprovalRequest

```
ApprovalRequest(
    server_name: str,
    tool_name: str,
    tool_args: dict[str, Any],
    respond: Callable[[bool], Awaitable[None]],
)
```

An MCP tool call approval request.

`ApprovalRequest` instances are passed to the approval callback registered with ApprovalClient. The callback must call accept or reject for making an approval decision.

Example

```
async def on_approval_request(request: ApprovalRequest):
    print(f"Approval request: {request}")
    if request.tool_name == "dangerous_tool":
        await request.reject()
    else:
        await request.accept()
```

Parameters:

| Name          | Type                                | Description                                | Default    |
| ------------- | ----------------------------------- | ------------------------------------------ | ---------- |
| `server_name` | `str`                               | Name of the MCP server providing the tool. | *required* |
| `tool_name`   | `str`                               | Name of the tool to execute.               | *required* |
| `tool_args`   | `dict[str, Any]`                    | Arguments to pass to the tool.             | *required* |
| `respond`     | `Callable[[bool], Awaitable[None]]` | Function to make an approval decision.     | *required* |

### accept

```
accept()
```

Accept the approval request.

### reject

```
reject()
```

Reject the approval request.

## ipybox.tool_exec.approval.server.ApprovalChannel

```
ApprovalChannel(
    approval_required: bool = False,
    approval_timeout: float | None = None,
)
```

Server-side channel for tool call approval over WebSocket.

`ApprovalChannel` accepts WebSocket connections from an ApprovalClient, sends approval requests via JSON-RPC, and processes approval responses.

When `approval_required` is `False`, all approval requests are automatically granted. When `True`, requests are sent to the connected `ApprovalClient` and the channel waits for a response within the configured timeout.

Parameters:

| Name                | Type    | Description                                      | Default                                                                   |
| ------------------- | ------- | ------------------------------------------------ | ------------------------------------------------------------------------- |
| `approval_required` | `bool`  | Whether approval is required for tool execution. | `False`                                                                   |
| `approval_timeout`  | \`float | None\`                                           | Timeout in seconds for approval requests. If None, no timeout is applied. |

### open

```
open: bool
```

Whether an `ApprovalClient` is currently connected.

### connect

```
connect(websocket: WebSocket)
```

Accept a WebSocket connection and process approval responses.

This method runs until the WebSocket disconnects.

Parameters:

| Name        | Type        | Description                         | Default    |
| ----------- | ----------- | ----------------------------------- | ---------- |
| `websocket` | `WebSocket` | The WebSocket connection to accept. | *required* |

### disconnect

```
disconnect()
```

Disconnect the WebSocket and error all pending approval requests.

### join

```
join(timeout: float = 5)
```

Wait for the this approval channel to close.

Parameters:

| Name      | Type    | Description                 | Default |
| --------- | ------- | --------------------------- | ------- |
| `timeout` | `float` | Timeout in seconds to wait. | `5`     |

### request

```
request(
    server_name: str,
    tool_name: str,
    tool_args: dict[str, Any],
) -> bool
```

Request approval for a tool call.

If `approval_required` is `False`, returns `True` immediately. Otherwise, sends an approval request to the connected `ApprovalClient` and waits for a response.

Parameters:

| Name          | Type             | Description                                | Default    |
| ------------- | ---------------- | ------------------------------------------ | ---------- |
| `server_name` | `str`            | Name of the MCP server providing the tool. | *required* |
| `tool_name`   | `str`            | Name of the tool to execute.               | *required* |
| `tool_args`   | `dict[str, Any]` | Arguments to pass to the tool.             | *required* |

Returns:

| Type   | Description                          |
| ------ | ------------------------------------ |
| `bool` | True if accepted, False if rejected. |

Raises:

| Type           | Description                        |
| -------------- | ---------------------------------- |
| `RuntimeError` | If no ApprovalClient is connected. |
| `TimeoutError` | If the approval request times out. |
