# Code execution

[`CodeExecutor`][ipybox.CodeExecutor] runs Python code, shell commands, and programmatic MCP tool calls in a stateful IPython kernel through a unified execution interface: all three can be combined in a single code block. Both tool calls and shell commands support application-level approval before execution.

```python
--8<-- "examples/codexec.py:imports"
```

## Basic execution

Use `execute()` for non-interactive execution where MCP tool calls and shell commands, if any, are auto-approved:

```python
--8<-- "examples/codexec.py:basic_execution"
```

For streaming output or application-level approval control, use `stream()` instead.

## Shell commands

Shell commands use IPython's `!` syntax:

```python
--8<-- "examples/codexec.py:shell_commands"
```

`!cmd` runs a shell command and prints its output. `result = !cmd` captures the output as a list of lines. Python variables are interpolated into shell commands via `{variable}` syntax. Shell commands and Python code mix freely in a single code block, for example to install packages with `!pip install` and use them immediately.

## Cell magics

For multi-line shell scripts, use `%%bash` or `%%sh` cell magics:

```python
--8<-- "examples/codexec.py:bash_magic"
```

`%%bash` must be the first line of the code block and passes the remaining lines to bash as a script. `%%sh` works the same way with `sh`. Unlike `!cmd`, cell magics cannot be mixed with Python code and do not support Python variable interpolation.

## Tool calls

ipybox can [generate typed Python APIs](apigen.md) from MCP server tool schemas. The generated code executes within the kernel, while MCP servers run on a separate [tool server](architecture.md).

## Approval

### Tool calls

When code calls a generated tool API, ipybox suspends execution and yields an `ApprovalRequest`. Call `accept()` to continue:

```python
--8<-- "examples/codexec.py:basic_approval"
```

`ApprovalRequest` includes `tool_name` and `tool_args` for inspection. Calling `reject()` raises a [`CodeExecutionError`][ipybox.CodeExecutionError] containing an `ApprovalRejectedError` traceback from the kernel.

`approve_tool_calls` (default `True`) is set explicitly in the example above. Set it to `False` to skip approval and execute tool calls directly when using `stream()`. The `execute()` method always auto-approves tool calls regardless of this setting.

### Shell commands

Enable `approve_shell_cmds=True` to require application-level approval for shell commands:

```python
--8<-- "examples/codexec.py:shell_approval"
```

Each `!cmd` triggers an `ApprovalRequest` with `tool_name="shell"` and `tool_args={"cmd": "..."}`, using the same approval interface as tool calls. Variable interpolation happens before the approval request, so the application sees the fully expanded command.

`%%bash` and `%%sh` cell magics also trigger approval when `approve_shell_cmds=True`, with `tool_name="shell_magic"` and `tool_args={"cmd": "..."}` containing the cell body:

```python
--8<-- "examples/codexec.py:bash_magic_approval"
```

#### Preventing bypass

Code could bypass shell command approval through various process-creation APIs (`subprocess`, `os.system()`, `os.exec*()`, `os.spawn*()`, `os.posix_spawn()`, `pty.spawn()`). Set `require_shell_escape=True` to guard these, forcing all shell execution through `!cmd` or `%%bash`/`%%sh` where it triggers the approval flow:

```python
--8<-- "examples/codexec.py:subprocess_blocking"
```

With `require_shell_escape=True`, direct process-creation calls raise a `RuntimeError`. Shell commands via `!cmd` and `%%bash`/`%%sh` still work and go through the approval channel. Requires `approve_shell_cmds=True`.

!!! note
    These guards are Python-level guards that close the most obvious gaps. They catch accidental bypass (e.g., an LLM agent reaching for `subprocess.run`) but are not a security boundary: code running in the kernel can undo guards, call C functions via `ctypes`, or use CPython internal modules. These bypasses can be prevented at the OS level. A future version will add [sandbox](sandbox.md)-level enforcement for shell command approval.

## Stream output chunks

Enable `chunks=True` to receive output incrementally as it's produced:

```python
--8<-- "examples/codexec.py:basic_chunks"
```

[`CodeExecutionChunk`][ipybox.CodeExecutionChunk] events contain partial output. The final [`CodeExecutionResult`][ipybox.CodeExecutionResult] contains the complete, aggregated output.

## Capturing plots

Plots are automatically captured as PNG files. Set `images_dir` to specify the output directory:

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

The IPython kernel does not inherit environment variables from the parent process. Pass them with `kernel_env`:

```python
--8<-- "examples/codexec.py:kernel_environment"
```

!!! note

    Environment variables referenced in `server_params` via `${VAR_NAME}` are taken from the parent process and do not need to be passed to `kernel_env`.

## Kernel reset

`reset()` clears all variables and definitions:

```python
--8<-- "examples/codexec.py:kernel_reset"
```

This also stops any MCP servers started during execution. They restart lazily on their next tool call.

## Resetting working directory

If `working_dir` is set, the kernel starts in that directory and ipybox resets
it back after each execution if code changed it. When a reset happens, ipybox
prints a message in the cell output.

```python
--8<-- "examples/codexec.py:working_directory_reset"
```

If `working_dir` is not set, ipybox preserves the default IPython behavior:
code can change the current working directory and that change persists until
code changes it again or the kernel is reset.

```python
--8<-- "examples/codexec.py:working_directory_persistent"
```
