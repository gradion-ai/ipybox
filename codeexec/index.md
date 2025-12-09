# Code execution

```python
from ipybox import (
    ApprovalRequest,
    CodeExecutionChunk,
    CodeExecutionResult,
    CodeExecutor,
)
```

CodeExecutor runs Python code in an IPython kernel where variables and definitions persist across executions.

## Basic execution

Use `execute()` for non-interactive execution where MCP tool calls, if any, are auto-approved:

```python
async with CodeExecutor() as executor:
    result = await executor.execute("print('hello world')")
    assert result.text == "hello world"
```

For application-level approval control, use `stream()` instead.

## Tool call approval

When code calls the [generated Python tool API](https://gradion-ai.github.io/ipybox/apigen/index.md), ipybox suspends execution and yields an ApprovalRequest. You must call `accept()` to continue execution:

```python
code = """
from mcptools.brave_search.brave_image_search import Params, Result, run

result: Result = run(Params(query="neural topic models", count=3))
print(f"num results = {len(result.items)}")
"""
async with CodeExecutor() as executor:
    async for item in executor.stream(code):
        match item:
            case ApprovalRequest():
                assert item.tool_name == "brave_image_search"
                assert item.tool_args["query"] == "neural topic models"
                assert item.tool_args["count"] == 3
                await item.accept()
            case CodeExecutionResult():
                assert item.text == "num results = 3"
```

The approval request includes `tool_name` and `tool_args` so you can inspect what's being called. Calling `reject()` raises a CodeExecutionError.

## Stream output chunks

Enable `chunks=True` to receive output incrementally as it's produced:

```python
code = """
from time import sleep
print("chunk 1")
sleep(0.5)
print("chunk 2")
"""
async with CodeExecutor() as executor:
    async for item in executor.stream(code, chunks=True):
        match item:
            case CodeExecutionChunk():
                assert item.text.strip() in ["chunk 1", "chunk 2"]
            case CodeExecutionResult():
                assert item.text == "chunk 1\nchunk 2"
```

CodeExecutionChunk events contain partial output. The final CodeExecutionResult still contains the complete output.

## Capturing plots

Plots are automatically captured as PNG files in the `images` directory. Use `images_dir` to customize the location:

```python
code = """
import matplotlib.pyplot as plt
plt.plot([1, 2, 3], [1, 4, 9])
plt.show()
"""
with tempfile.TemporaryDirectory() as images_dir:
    async with CodeExecutor(images_dir=Path(images_dir)) as executor:
        result = await executor.execute(code)
        assert len(result.images) == 1
        assert result.images[0].exists()
        assert result.images[0].suffix == ".png"
```

Generated images are available in `result.images` as a list of `Path` objects.

## Custom timeouts

Configure approval and execution timeouts:

```python
# set custom approval timeout, default is 60 seconds
async with CodeExecutor(approval_timeout=10) as executor:
    # set custom execution timeout, default is 120 seconds
    async for item in executor.stream("...", timeout=10):
        ...
```

- `approval_timeout`: How long to wait for `accept()`/`reject()` (default: 60s)
- `timeout` in `stream()`: Maximum total execution time including approval waits (default: 120s)

## Kernel environment

The IPython kernel does not inherit environment variables from the parent process. You can pass them explicitly with `kernel_env`:

```python
# IPython kernel does not inherit environment variables from parent process
# Kernel environment must be explicitly set using the kernel_env parameter
async with CodeExecutor(kernel_env={"TEST_VAR": "test_val"}) as executor:
    result = await executor.execute("import os; print(os.environ['TEST_VAR'])")
    assert result.text == "test_val"
```

Note

Environment variables referenced in `server_params` via `${VAR_NAME}` are taken from the parent process and do not need to be passed to `kernel_env`.

## Kernel reset

Clear all variables and definitions by resetting the IPython kernel with `reset()`:

```python
async with CodeExecutor() as executor:
    await executor.execute("x = 42")
    result = await executor.execute("print(x)")
    assert result.text == "42"

    await executor.reset()

    code = """
    try:
        print(x)
    except NameError:
        print("x not defined")
    """
    result = await executor.execute(code)
    assert result.text == "x not defined"
```

This also stops any MCP servers started during execution. They restart lazily on their next tool call.

## Working directory

The kernel shares the working directory with the parent process:

```python
async with CodeExecutor() as executor:
    import os

    result = await executor.execute("import os; print(os.getcwd())")
    assert result.text == os.getcwd()
```
