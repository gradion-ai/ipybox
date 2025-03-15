# Usage

The two main classes of the `ipybox` package are [`ExecutionContainer`](api/execution_container.md) and [`ExecutionClient`](api/execution_client.md).

!!! Note

    Runnable scripts of the source code on this page are available in the [examples](https://github.com/gradion-ai/ipybox/tree/main/examples) directory.

## Basic usage

For executing code in `ipybox` you first need to create a Docker container from an `ipybox` [Docker image](installation.md#docker-image) and then an IPython kernel running in that container. This is done with the `ExecutionContainer` and the `ExecutionClient` context managers.

```python
--8<-- "examples/01_basic_usage.py:import"

--8<-- "examples/01_basic_usage.py:usage"
```

1. Create and start a container for code execution
2. Create and connect to an IPython kernel
3. Execute Python code and await the result
4. Output: `Hello, world!`

The default image used by `ExecutionContainer` is `gradion-ai/ipybox`. You can specify a custom image with the `tag` argument like in `ExecutionContainer(tag="my-box:v1")`, for example.

!!! Note

    Instead of letting the `ExecutionContainer` context manager handle the lifecycle of the container, you can also [manually manage the container lifecycle](usage.md#manual-container-lifecycle-management).


## State management

Code execution within the same `client` context is stateful i.e. you can reference variables from previous executions. Code executions in different client contexts are isolated from each other:

```python
--8<-- "examples/02_state_management.py:usage"
```

1. First client context
2. Execute code that defines variable x
3. Reference variable x defined in previous execution
4. Second client context
5. Variable x is not defined in `client_2` context

## Output streaming

The `ExecutionClient` supports streaming output as it's generated during code execution:

```python
--8<-- "examples/03_output_streaming.py:usage"
```

1. Code that produces gradual output
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
5. Get the aggregated output as a single result
6. Prints the aggregated output:
    ```
    Aggregated output:
    Processing step 0
    Processing step 1
    Processing step 2
    Processing step 3
    Processing step 4
    ```

The `stream()` method accepts an optional `timeout` argument (defaults to `120` seconds). In case of timeout, the execution is automatically terminated by interrupting the kernel.

## Installing dependencies at runtime

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

You can also install and use a package within a single execution. There's no need to have two separate executions as done in the example above.

## Creating and returning plots

Plots created with `matplotlib` or other libraries are returned as [PIL](https://pillow.readthedocs.io) images. Images are not part of the output stream, but are available as `images` list in the `result` object.

```python
--8<-- "examples/05_creating_plots.py:usage"
```

1. Install `matplotlib` and generate a plot
2. Stream output text (installation progress and `print` statement)
3. Get attached image from execution result and save it as [sine.png](img/sine.png)

## Bind mounts

Bind mounts allow executed code to read and write files on the host machine.

```python
--8<-- "examples/06_bind_mounts.py:usage"
```

1. Map host paths to container paths.
2. For reading files from host.
3. For writing files to host.
4. Read from mounted `data` directory, convert to uppercase and write to mounted `output` directory
5. Verify the results on host

## Environment variables

Environment variables can be set on the container for passing secrets or configuration data, for example.

```python
--8<-- "examples/07_environment_variables.py:usage"
```

1. Define environment variables for the container
2. Access environment variables in executed code
3. Prints
    ```
    Using API key: secret-key-123
    Debug mode enabled
    ```

## Manual container lifecycle management

Instead of using `ExecutionContainer` as a context manager, you can also manually `run()` and `kill()` the container. Setting a user-defined port (e.g. `7777` in the example below) is optional.


This is useful for running the container on a separate host listening to a user-defined host port (e.g. `7777` in the example below).

```python
--8<-- "examples/08_manual_lifecycle.py:run-container"

# do some work ...

--8<-- "examples/08_manual_lifecycle.py:kill-container"
```

1. Create an `ExecutionContainer` instance using a fixed port.
2. Run the container (detached).
3. Cleanup.


## Using a remote `DOCKER_HOST`

If you want to run the execution container on a remote host but want to manage the container locally, you can set the `DOCKER_HOST` [environment variable](https://docs.docker.com/reference/cli/docker/#environment-variables) to the remote host. The following example assumes that the remote Docker daemon has been configured to accept `tcp` connections at port `2375`.

```python
--8<-- "examples/09_remote_docker_host.py:usage"
```

1. Example IP address of the remote Docker host
2. Remote Docker daemon is accessible via `tcp` at port `2375`
3. Creates a container on the remote host
4. Create an IPython kernel in the remote container
