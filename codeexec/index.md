# Code execution

CodeExecutor runs Python code, shell commands, and programmatic MCP tool calls in a stateful IPython kernel through a unified execution interface: all three can be combined in a single code block. Both tool calls and shell commands support application-level approval before execution.

```
from ipybox import (
    ApprovalRequest,
    CodeExecutionChunk,
    CodeExecutionResult,
    CodeExecutor,
)
```

## Basic execution

Use `execute()` for non-interactive execution where MCP tool calls and shell commands, if any, are auto-approved:

```
async with CodeExecutor() as executor:
    result = await executor.execute("print('hello world')")
    assert result.text == "hello world"
```

For streaming output or application-level approval control, use `stream()` instead.

## Shell commands

Shell commands use IPython's `!` syntax:

```
async with CodeExecutor() as executor:
    # Run a shell command
    result = await executor.execute("!echo hello from shell")
    assert result.text == "hello from shell"

    # Capture shell output into a Python variable
    code = """
    files = !ls /tmp
    print(f"found {len(files)} entries")
    """
    result = await executor.execute(code)

    # Variable interpolation in shell commands
    code = """
    name = "world"
    !echo hello {name}
    """
    result = await executor.execute(code)
    assert result.text == "hello world"
```

`!cmd` runs a shell command and prints its output. `result = !cmd` captures the output as a list of lines. Python variables are interpolated into shell commands via `{variable}` syntax. Shell commands and Python code mix freely in a single code block, for example to install packages with `!pip install` and use them immediately.

## Cell magics

For multi-line shell scripts, use `%%bash` or `%%sh` cell magics:

```
code = """
%%bash
for i in 1 2 3; do
  echo $i
done
"""

async with CodeExecutor() as executor:
    result = await executor.execute(code)
    assert result.text == "1\n2\n3"
```

`%%bash` must be the first line of the code block and passes the remaining lines to bash as a script. `%%sh` works the same way with `sh`. Unlike `!cmd`, cell magics cannot be mixed with Python code and do not support Python variable interpolation.

## Tool calls

ipybox can [generate typed Python APIs](https://gradion-ai.github.io/ipybox/apigen/index.md) from MCP server tool schemas. The generated code executes within the kernel, while MCP servers run on a separate [tool server](https://gradion-ai.github.io/ipybox/architecture/index.md).

## Approval

### Tool calls

When code calls a generated tool API, ipybox suspends execution and yields an `ApprovalRequest`. Call `accept()` to continue:

```
code = """
from mcptools.brave_search.brave_image_search import Params, Result, run

result: Result = run(Params(query="neural topic models", count=3))
print(f"num results = {len(result.items)}")
"""
async with CodeExecutor(approve_tool_calls=True) as executor:  # default
    async for item in executor.stream(code):
        match item:
            case ApprovalRequest(tool_name=name, tool_args=args):
                assert name == "brave_image_search"
                assert args["query"] == "neural topic models"
                assert args["count"] == 3
                await item.accept()
            case CodeExecutionResult():
                assert item.text == "num results = 3"
```

`ApprovalRequest` includes `tool_name` and `tool_args` for inspection. Calling `reject()` raises a CodeExecutionError containing an `ApprovalRejectedError` traceback from the kernel.

`approve_tool_calls` (default `True`) is set explicitly in the example above. Set it to `False` to skip approval and execute tool calls directly when using `stream()`. The `execute()` method always auto-approves tool calls regardless of this setting.

### Shell commands

Enable `approve_shell_cmds=True` to require application-level approval for shell commands:

```
code = """
name = "world"
!echo hello {name}
"""
async with CodeExecutor(approve_shell_cmds=True) as executor:
    async for item in executor.stream(code):
        match item:
            case ApprovalRequest(tool_name="shell", tool_args=args):
                assert args == {"cmd": "echo hello world"}
                await item.accept()
            case CodeExecutionResult():
                assert item.text == "hello world"
```

Each `!cmd` triggers an `ApprovalRequest` with `tool_name="shell"` and `tool_args={"cmd": "..."}`, using the same approval interface as tool calls. Variable interpolation happens before the approval request, so the application sees the fully expanded command.

`%%bash` and `%%sh` cell magics also trigger approval when `approve_shell_cmds=True`, with `tool_name="shell_magic"` and `tool_args={"cmd": "..."}` containing the cell body:

```
code = """
%%bash
echo hello from bash
"""

async with CodeExecutor(approve_shell_cmds=True) as executor:
    async for item in executor.stream(code):
        match item:
            case ApprovalRequest(tool_name="shell_magic", tool_args=args):
                assert "echo hello from bash" in args["cmd"]
                await item.accept()
            case CodeExecutionResult():
                assert item.text == "hello from bash"
```

#### Preventing bypass

Code could bypass shell command approval through various process-creation APIs (`subprocess`, `os.system()`, `os.exec*()`, `os.spawn*()`, `os.posix_spawn()`, `pty.spawn()`). Set `require_shell_escape=True` to guard these, forcing all shell execution through `!cmd` or `%%bash`/`%%sh` where it triggers the approval flow:

```
async with CodeExecutor(approve_shell_cmds=True, require_shell_escape=True) as executor:
    # Direct subprocess calls are blocked to prevent bypassing approval
    try:
        await executor.execute('import subprocess; subprocess.run(["echo", "hi"])')
    except Exception as e:
        assert "RuntimeError" in str(e)

    # Shell commands via !cmd still work and go through approval
    async for item in executor.stream("!echo hello"):
        match item:
            case ApprovalRequest():
                await item.accept()
            case CodeExecutionResult():
                assert item.text == "hello"
```

With `require_shell_escape=True`, direct process-creation calls raise a `RuntimeError`. Shell commands via `!cmd` and `%%bash`/`%%sh` still work and go through the approval channel. Requires `approve_shell_cmds=True`.

Note

These guards are Python-level guards that close the most obvious gaps. They catch accidental bypass (e.g., an LLM agent reaching for `subprocess.run`) but are not a security boundary: code running in the kernel can undo guards, call C functions via `ctypes`, or use CPython internal modules. These bypasses can be prevented at the OS level. A future version will add [sandbox](https://gradion-ai.github.io/ipybox/sandbox/index.md)-level enforcement for shell command approval.

## Stream output chunks

Enable `chunks=True` to receive output incrementally as it's produced:

```
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

CodeExecutionChunk events contain partial output. The final CodeExecutionResult contains the complete, aggregated output.

## Capturing plots

Plots are automatically captured as PNG files. Set `images_dir` to specify the output directory:

```
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

```
# set custom approval timeout, default is no timeout
async with CodeExecutor(approval_timeout=10) as executor:
    # set custom execution timeout, default is no timeout
    async for item in executor.stream("...", timeout=10):
        ...
```

- `approval_timeout`: How long to wait for `accept()`/`reject()` (default: no timeout)
- `timeout` in `stream()`: Maximum total execution time **excluding approval waits**. Tool execution time and kernel execution time still count toward this budget (default: no timeout).

## Kernel environment

The IPython kernel does not inherit environment variables from the parent process. Pass them with `kernel_env`:

```
# IPython kernel does not inherit environment variables from parent process
# Kernel environment must be explicitly set using the kernel_env parameter
async with CodeExecutor(kernel_env={"TEST_VAR": "test_val"}) as executor:
    result = await executor.execute("import os; print(os.environ['TEST_VAR'])")
    assert result.text == "test_val"
```

Note

Environment variables referenced in `server_params` via `${VAR_NAME}` are taken from the parent process and do not need to be passed to `kernel_env`.

## Kernel reset

`reset()` clears all variables and definitions:

```
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

## Resetting working directory

If `working_dir` is set, the kernel starts in that directory and ipybox resets it back after each execution if code changed it. When a reset happens, ipybox prints a message in the cell output.

```
base_dir = Path.cwd()

with tempfile.TemporaryDirectory() as changed_dir:
    async with CodeExecutor(working_dir=base_dir) as executor:
        result = await executor.execute(f"import os; os.chdir({changed_dir!r})")
        assert result.text == f"[ipybox] cwd reset to {base_dir}"

        result = await executor.execute("import os; print(os.getcwd())")
        assert result.text == str(base_dir)
```

If `working_dir` is not set, ipybox preserves the default IPython behavior: code can change the current working directory and that change persists until code changes it again or the kernel is reset.

```
with tempfile.TemporaryDirectory() as changed_dir:
    async with CodeExecutor() as executor:
        await executor.execute(f"import os; os.chdir({changed_dir!r})")

        result = await executor.execute("import os; print(os.getcwd())")
        assert result.text == changed_dir
```
