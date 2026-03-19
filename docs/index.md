![ipybox](images/ipybox-crop-nobg.png){ width="300" style="margin-bottom: 1.5em" }

# ipybox

ipybox is a local, sandboxed execution environment for running Python code, shell commands and programmatic MCP tool calls with a unified execution model.

ipybox executes Python code and shell commands in a stateful IPython kernel. Definitions and variables persist across executions, and kernels can be sandboxed with [sandbox-runtime](https://github.com/anthropic-experimental/sandbox-runtime), enforcing filesystem and network restrictions on OS-level.

It can generate Python APIs for MCP server tools via [mcpygen](https://gradion-ai.github.io/mcpygen/), and supports application-level approval of programmatic MCP tool calls and shell commands during execution. ipybox runs locally on your computer, enabling protected access to your local data and tools.

ipybox enables AI agents to execute both Python code and shell commands with a unified execution model, further reducing the number of LLM inference rounds. Python code, shell commands, and programmatic MCP tool calls can be mixed in a code block generated in a single inference pass.

## Capabilities

| Capability | Description |
| --- | --- |
| **Stateful code execution** | State persists across executions in IPython kernels |
| **Unified execution model** | Mix Python code, shell commands, and programmatic MCP tool calls in a single code block |
| **Shell command execution** | Run shell commands via `!cmd` syntax, capture output into Python variables |
| **Programmatic MCP tool calling** | MCP tools called via generated Python API ("code mode"), not JSON directly |
| **Python tool API generation** | Typed functions and Pydantic models generated from MCP tool schemas via [mcpygen](https://gradion-ai.github.io/mcpygen/) |
| **Application-level approval** | Optional approval of tool calls and shell commands before execution |
| **Lightweight sandboxing** | Optional kernel isolation via Anthropic's [sandbox-runtime](https://github.com/anthropic-experimental/sandbox-runtime) |
| **Local code execution** | No cloud dependencies, everything runs locally on your machine |

## Usage

| Component | Description |
| --- | --- |
| **[Python SDK](api/code_executor.md)** | Python API for building applications on ipybox |
| **[MCP server](mcpserver.md)** | ipybox as MCP server for code actions and programmatic tool calling |
| **[Claude Code plugin](ccplugin.md)** | Plugin that bundles the ipybox MCP server and a code action skill |

!!! tip "freeact"

    [Freeact](https://gradion-ai.github.io/freeact/) is a general-purpose agent built on ipybox.
