# Code Execution

`CodeExecutor` runs Python code in an IPython kernel where variables and definitions persist across executions.

```python
--8<-- "examples/codexec.py:imports"
```

## Basic execution

Use `execute()` for non-interactive execution where MCP tool calls, if any, are auto-approved:

```python
--8<-- "examples/codexec.py:basic_execution"
```

`execute()` auto-approves all tool calls. For explicit approval control, use `stream()` instead.

## Tool call approval

When code calls a generated MCP wrapper, ipybox yields an `ApprovalRequest`. You must call `accept()` or `reject()` before execution continues:

```python
--8<-- "examples/codexec.py:basic_approval"
```

The request includes `tool_name` and `tool_args` so you can inspect what's being called.

## Stream output chunks

Enable `chunks=True` to receive output incrementally as it's produced:

```python
--8<-- "examples/codexec.py:basic_chunks"
```

`CodeExecutionChunk` events contain partial output. The final `CodeExecutionResult` still contains the complete output.

## Capturing plots

Set `images_dir` to capture plots as PNG files:

```python
--8<-- "examples/codexec.py:basic_plotting"
```

Generated images are available in `result.images` as a list of `Path` objects.

## Custom timeouts

Configure approval and execution timeouts:

```python
--8<-- "examples/codexec.py:custom_timeouts"
```

- `approval_timeout`: How long to wait for `accept()`/`reject()` (default: 60s)
- `timeout` in `stream()`: Maximum total execution time including approval waits (default: 120s)

## Kernel environment

The IPython kernel does not inherit environment variables from the parent process. Pass them explicitly:

```python
--8<-- "examples/codexec.py:kernel_environment"
```

## Kernel reset

Clear all variables and definitions by resetting the IPython kernel with `reset()`:

```python
--8<-- "examples/codexec.py:kernel_reset"
```

This also stops any MCP servers started during execution. They restart lazily on their next tool call.

## Working directory

The kernel shares the working directory with the parent process:

```python
--8<-- "examples/codexec.py:working_directory"
```

## Next steps

- [Sandboxing](sandbox.md) - Secure execution with network and filesystem isolation
