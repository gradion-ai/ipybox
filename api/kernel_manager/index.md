## ipybox.kernel_mgr.server.KernelGateway

```
KernelGateway(
    host: str = "localhost",
    port: int = 8888,
    sandbox: bool = False,
    sandbox_config: Path | None = None,
    log_level: str = "INFO",
    log_to_stderr: bool = False,
    env: dict[str, str] | None = None,
)
```

Manages a Jupyter Kernel Gateway process.

The kernel gateway provides a REST and WebSocket API for creating and communicating with IPython kernels. Use KernelClient to create and connect to an IPython kernel and execute code.

When sandboxing is enabled, the gateway runs inside Anthropic's [sandbox-runtime](https://github.com/anthropic-experimental/sandbox-runtime), providing secure isolation for code execution.

Example

```
async with KernelGateway(host="localhost", port=8888) as gateway:
    # Gateway is running, connect with KernelClient
    await gateway.join()  # Wait until gateway stops
```

Parameters:

| Name             | Type             | Description                                            | Default                                                                                                                                                                                       |
| ---------------- | ---------------- | ------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `host`           | `str`            | Hostname or IP address to bind the gateway to.         | `'localhost'`                                                                                                                                                                                 |
| `port`           | `int`            | Port number the gateway listens on.                    | `8888`                                                                                                                                                                                        |
| `sandbox`        | `bool`           | Whether to run the gateway inside the sandbox-runtime. | `False`                                                                                                                                                                                       |
| `sandbox_config` | \`Path           | None\`                                                 | Path to a JSON file with sandbox configuration. See the Configuration section of the sandbox-runtime README for available options.                                                            |
| `log_level`      | `str`            | Logging level for the gateway process.                 | `'INFO'`                                                                                                                                                                                      |
| `log_to_stderr`  | `bool`           | Whether to redirect gateway logs to stderr.            | `False`                                                                                                                                                                                       |
| `env`            | \`dict[str, str] | None\`                                                 | Environment variables to set for kernels created by the gateway. Kernels do not inherit environment variables from the parent process, so any required variables must be explicitly provided. |

### join

```
join()
```

Waits for the kernel gateway process to exit.

### start

```
start()
```

Starts the kernel gateway process.

Raises:

| Type           | Description                        |
| -------------- | ---------------------------------- |
| `RuntimeError` | If the gateway is already running. |

### stop

```
stop(timeout: float = 10)
```

Stops the kernel gateway process.

Terminates the gateway and all child processes. If the process doesn't stop within the timeout, it is forcefully killed.

Parameters:

| Name      | Type    | Description                                               | Default |
| --------- | ------- | --------------------------------------------------------- | ------- |
| `timeout` | `float` | Maximum time in seconds to wait for graceful termination. | `10`    |

## ipybox.kernel_mgr.client.KernelClient

```
KernelClient(
    host: str = "localhost",
    port: int = 8888,
    images_dir: Path | None = None,
    ping_interval: float = 10,
)
```

Client for executing code in an IPython kernel.

Connects to a KernelGateway to create and communicate with an IPython kernel. Code execution is stateful: definitions and variables from previous executions are available to subsequent executions.

Example

```
async with KernelClient(host="localhost", port=8888) as client:
    # Simple execution
    result = await client.execute("print('hello')")
    print(result.text)

    # Streaming execution
    async for item in client.stream("print('hello')"):
        match item:
            case str():
                print(f"Chunk: {item}")
            case ExecutionResult():
                print(f"Result: {item}")
```

Parameters:

| Name            | Type    | Description                                                                                   | Default                                                                                                   |
| --------------- | ------- | --------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| `host`          | `str`   | Hostname or IP address of the kernel gateway.                                                 | `'localhost'`                                                                                             |
| `port`          | `int`   | Port number of the kernel gateway.                                                            | `8888`                                                                                                    |
| `images_dir`    | \`Path  | None\`                                                                                        | Directory for saving images generated during code execution. Defaults to images in the current directory. |
| `ping_interval` | `float` | Interval in seconds for WebSocket pings that keep the connection to the IPython kernel alive. | `10`                                                                                                      |

### kernel_id

```
kernel_id
```

The ID of the running IPython kernel.

Raises:

| Type           | Description                   |
| -------------- | ----------------------------- |
| `RuntimeError` | If not connected to a kernel. |

### connect

```
connect(retries: int = 10, retry_interval: float = 1.0)
```

Creates an IPython kernel and connects to it.

Parameters:

| Name             | Type    | Description                                  | Default |
| ---------------- | ------- | -------------------------------------------- | ------- |
| `retries`        | `int`   | Number of connection retries.                | `10`    |
| `retry_interval` | `float` | Delay between connection retries in seconds. | `1.0`   |

Raises:

| Type           | Description                                            |
| -------------- | ------------------------------------------------------ |
| `RuntimeError` | If connection cannot be established after all retries. |

### disconnect

```
disconnect()
```

Disconnects from and deletes the running IPython kernel.

### execute

```
execute(
    code: str, timeout: float | None = None
) -> ExecutionResult
```

Executes code in this client's IPython kernel and returns the result.

Waits for execution to complete and returns the final result. Use stream for incremental output.

Parameters:

| Name      | Type    | Description             | Default                                                                                   |
| --------- | ------- | ----------------------- | ----------------------------------------------------------------------------------------- |
| `code`    | `str`   | Python code to execute. | *required*                                                                                |
| `timeout` | \`float | None\`                  | Maximum time in seconds to wait for the execution result. If None, no timeout is applied. |

Returns:

| Type              | Description                                                       |
| ----------------- | ----------------------------------------------------------------- |
| `ExecutionResult` | The execution result containing output text and generated images. |

Raises:

| Type             | Description                                     |
| ---------------- | ----------------------------------------------- |
| `ExecutionError` | If code execution raises an error.              |
| `TimeoutError`   | If code execution duration exceeds the timeout. |

### reset

```
reset()
```

Resets the IPython kernel to a clean state.

Deletes the running kernel and creates a new one.

### stream

```
stream(
    code: str, timeout: float | None = None
) -> AsyncIterator[str | ExecutionResult]
```

Executes code in this client's IPython kernel.

Yields output chunks as strings during execution, and yields the final ExecutionResult as the last item.

Parameters:

| Name      | Type    | Description             | Default                                                                                   |
| --------- | ------- | ----------------------- | ----------------------------------------------------------------------------------------- |
| `code`    | `str`   | Python code to execute. | *required*                                                                                |
| `timeout` | \`float | None\`                  | Maximum time in seconds to wait for the execution result. If None, no timeout is applied. |

Yields:

| Name              | Type                 | Description         |
| ----------------- | -------------------- | ------------------- |
| `str`             | \`AsyncIterator\[str | ExecutionResult\]\` |
| `ExecutionResult` | \`AsyncIterator\[str | ExecutionResult\]\` |

Raises:

| Type             | Description                                     |
| ---------------- | ----------------------------------------------- |
| `ExecutionError` | If code execution raises an error.              |
| `TimeoutError`   | If code execution duration exceeds the timeout. |

## ipybox.kernel_mgr.client.ExecutionResult

```
ExecutionResult(text: str | None, images: list[Path])
```

The result of a successful code execution.

Attributes:

| Name     | Type         | Description                                         |
| -------- | ------------ | --------------------------------------------------- |
| `text`   | \`str        | None\`                                              |
| `images` | `list[Path]` | List of paths to images generated during execution. |

## ipybox.kernel_mgr.client.ExecutionError

Bases: `Exception`

Raised when code executed in an IPython kernel raises an error.
