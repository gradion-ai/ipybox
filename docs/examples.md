# Usage

!!! Info

    Code examples in the following sections are from the project's [examples](https://github.com/gradion-ai/ipybox/tree/main/examples) directory. Most of them use a prebuilt [Docker image](docker.md).

## Basic usage

Use the [`ExecutionContainer`][ipybox.container.ExecutionContainer] context manager to create a container from an `ipybox` Docker image. The container is created on entering the context manager and removed on exit.
Use the [`ExecutionClient`][ipybox.executor.ExecutionClient] context manager to manage the lifecycle of an IPython kernel within the container. A kernel is created on entering the context manager and removed on exit.
Call [`execute`][ipybox.executor.ExecutionClient.execute] on an `ExecutionClient` instance to execute code in its kernel.

```python
--8<-- "examples/01_basic_usage.py:import"

--8<-- "examples/01_basic_usage.py:usage"
```

1. Create and start a code execution container
2. Create an IPython kernel in the container
3. Execute Python code and await the result
4. Prints: `Output: Hello, world!`

The [`execute`][ipybox.executor.ExecutionClient.execute] method accepts an optional `timeout` argument (defaults to `120` seconds). On timeout, the execution is terminated by interrupting the kernel and a `TimeoutError` is raised.

!!! Info

    Instead of using the [`ExecutionContainer`][ipybox.container.ExecutionContainer] context manager for lifecycle management, you can also manually [`run`][ipybox.container.ExecutionContainer.run] and [`kill`][ipybox.container.ExecutionContainer.kill] a container.

    ```python
    --8<-- "examples/08_manual_lifecycle.py:run-container"

    # do some work ...

    --8<-- "examples/08_manual_lifecycle.py:kill-container"
    ```

    1. Create an `ExecutionContainer` instance.
    2. Run the container (detached).
    3. Kill the container.


## Stateful code execution

Code executions with the same [`ExecutionClient`][ipybox.executor.ExecutionClient] instance are stateful. Definitions and variables from previous executions can be used in later executions. Code executions with different `ExecutionClient` instances run in different kernels and do not share in-memory state.

```python
--8<-- "examples/02_state_management.py:usage"
```

1. First client instance
2. Execute code that defines variable `x`
3. Use variable `x` defined in previous execution
4. Second client instance
5. Variable `x` is not defined in `client_2`'s kernel

!!! note

    While kernels in the same container don't share in-memory state, they can still exchange data by reading and writing files to the shared container filesystem.
    For full isolation of code executions, you need to run them in different containers.

## Execution output streaming

Instead of waiting for code execution to complete, output can also be streamed as it is generated:

```python
--8<-- "examples/03_output_streaming.py:usage"
```

1. Code that produces gradual output every second
2. Submit the code for execution
3. Stream the output
4. Prints one line per second:
    ```
    Received output: Processing step 0
    Received output: Processing step 1
    Received output: Processing step 2
    Received output: Processing step 3
    Received output: Processing step 4
    ```
5. Get the aggregated output (returns immediately)
6. Prints the aggregated output:
    ```
    Aggregated output:
    Processing step 0
    Processing step 1
    Processing step 2
    Processing step 3
    Processing step 4
    ```

## Restrict network access

A container allows all outbound internet traffic by default. This can be restricted with the [`init_firewall`][ipybox.container.ExecutionContainer.init_firewall] method to a list of domain names, IP addresses, or CIDR ranges.

!!! Note
    For the following example, build the Docker image with `python -m ipybox build`. The firewall can only be initialized on containers running as a non-root user i.e. containers of `ipybox` images that were [built](docker.md#custom-image) **without** the `-r` or `-root` flag. An attempt to initialize the firewall on a container running as root will raise an error.

```python
--8<-- "examples/12_firewall_activation.py:import"

--8<-- "examples/12_firewall_activation.py:usage"
```

1. Internet access is not restricted before firewall initialization
2. Restrict internet access to domain `gradion.ai`
3. Allowed by firewall
4. Blocked by firewall. May take longer than the configured 1 second timeout because `example.com` resolves to multiple IP addresses and all are tried before failing.


## Install packages at runtime

Python packages can be installed at runtime by executing `!pip install <package>`:

```python
--8<-- "examples/04_installing_dependencies.py:usage"
```

1. Install the `einops` package using pip
2. Stream the installation progress. Something like
    ```
    Collecting einops
    Downloading einops-0.8.0-py3-none-any.whl (10.0 kB)
    Installing collected packages: einops
    Successfully installed einops-0.8.0
    ```
3. Import and use the installed package
4. Prints `Output: 0.8.0`

You can also install and use a package in a single execution step, as shown in the [next section](#generate-plots), for example.

## Generate plots

Plots generated with `matplotlib` and other visualization libraries are returned as [PIL](https://pillow.readthedocs.io) images. Images are not part of the output stream; they can be obtained from the [`result`][ipybox.executor.ExecutionResult] object as `images` list.

```python
--8<-- "examples/05_creating_plots.py:usage"
```

1. Install `matplotlib` and generate a plot
2. Stream output text (installation progress and `print` statement)
3. Get attached image from execution result and save it as [sine.png](img/sine.png)

## File operations

Files and directories can be transferred between the host and container using the [`ResourceClient`][ipybox.resource.client.ResourceClient].

```python
--8<-- "examples/11_file_operations.py:usage"
```

1. Upload a single file to the container
2. Upload an entire directory to the container
3. Copy files within the container
4. Download a file from the container
5. Download a directory from the container
6. Delete a file in the container

## Environment variables

Environment variables for the container can be passed to the [`ExecutionContainer`][ipybox.container.ExecutionContainer] constructor.

```python
--8<-- "examples/07_environment_variables.py:usage"
```

1. Set environment variables for the container
2. Access environment variables in executed code
3. Prints
    ```
    Using API key: secret-key-123
    Debug mode enabled
    ```


## Remote `DOCKER_HOST`

If you want to run a code execution container on a remote host but manage the container with [`ExecutionContainer`][ipybox.container.ExecutionContainer] locally, set the `DOCKER_HOST` [environment variable](https://docs.docker.com/reference/cli/docker/#environment-variables) to that host. The following example assumes that the [remote Docker daemon has been configured](https://docs.docker.com/engine/daemon/remote-access/) to accept `tcp` connections at port `2375`.

```python
--8<-- "examples/09_remote_docker_host.py:usage"
```

1. Example IP address of the remote Docker host
2. Remote Docker daemon is accessible via `tcp` at port `2375`
3. Creates a container on the remote host
4. Create an IPython kernel in the remote container

## MCP integration

`ipybox` exposes an [MCP server](mcp-server.md) interface for secure Python code execution accessible to MCP clients. `ipybox` can also [invoke other MCP servers](mcp-client.md) via automatically generated Python client code inside the container.
