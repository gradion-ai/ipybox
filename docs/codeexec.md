# Code execution

```python
--8<-- "examples/codexec.py:imports"
```

[`CodeExecutor`][ipybox.CodeExecutor] runs Python code in an IPython kernel where variables and definitions persist across executions.

## Basic execution

Use `execute()` for non-interactive execution where MCP tool calls, if any, are auto-approved:

```python
--8<-- "examples/codexec.py:basic_execution"
```

For application-level approval control, use `stream()` instead.

## Tool call approval

When code calls the [generated Python tool API](apigen.md), ipybox suspends execution and yields an `ApprovalRequest`. You must call `accept()` to continue execution:

```python
--8<-- "examples/codexec.py:basic_approval"
```

The approval request includes `tool_name` and `tool_args` so you can inspect what's being called. Calling `reject()` raises a [`CodeExecutionError`][ipybox.CodeExecutionError].

## Stream output chunks

Enable `chunks=True` to receive output incrementally as it's produced:

```python
--8<-- "examples/codexec.py:basic_chunks"
```

[`CodeExecutionChunk`][ipybox.CodeExecutionChunk] events contain partial output. The final [`CodeExecutionResult`][ipybox.CodeExecutionResult] still contains the complete output.

## Capturing plots

Plots are automatically captured as PNG files in the `images` directory. Use `images_dir` to customize the location:

```python
--8<-- "examples/codexec.py:basic_plotting"
```

Generated images are available in `result.images` as a list of `Path` objects.

## Custom timeouts

Configure approval and execution timeouts:

```python
--8<-- "examples/codexec.py:custom_timeouts"
```

- `approval_timeout`: How long to wait for `accept()`/`reject()` (default: no timeout)
- `timeout` in `stream()`: Maximum total execution time **excluding approval waits**. Tool execution time and kernel execution time still count toward this budget (default: no timeout).

## Kernel environment

The IPython kernel does not inherit environment variables from the parent process. You can pass them explicitly with `kernel_env`:

```python
--8<-- "examples/codexec.py:kernel_environment"
```

!!! note

    Environment variables referenced in `server_params` via `${VAR_NAME}` are taken from the parent process and do not need to be passed to `kernel_env`.

## Kernel reset

Clear all variables and definitions by resetting the IPython kernel with `reset()`:

```python
--8<-- "examples/codexec.py:kernel_reset"
```

This also stops any MCP servers started during execution. They restart lazily on their next tool call.

## Working directory

If `working_dir` is set, the kernel starts there and ipybox restores that
directory after each execution. When a reset happens, ipybox prints a message
in the cell output.

```python
--8<-- "examples/codexec.py:working_directory_reset"
```

If `working_dir` is not set, ipybox preserves the default IPython behavior:
code can change the current working directory and that change persists until
code changes it again or the kernel is reset.

```python
--8<-- "examples/codexec.py:working_directory_persistent"
```
