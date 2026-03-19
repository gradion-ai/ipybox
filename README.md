<p align="left">
    <img src="docs/images/ipybox-crop-nobg.png" alt="ipybox" width="300">
</p>

# ipybox

mcp-name: io.github.gradion-ai/ipybox

<p align="left">
    <a href="https://gradion-ai.github.io/ipybox/"><img alt="Website" src="https://img.shields.io/website?url=https%3A%2F%2Fgradion-ai.github.io%2Fipybox%2F&up_message=online&down_message=offline&label=docs"></a>
    <a href="https://pypi.org/project/ipybox/"><img alt="PyPI - Version" src="https://img.shields.io/pypi/v/ipybox?color=blue"></a>
    <a href="https://github.com/gradion-ai/ipybox/releases"><img alt="GitHub Release" src="https://img.shields.io/github/v/release/gradion-ai/ipybox"></a>
    <a href="https://github.com/gradion-ai/ipybox/actions"><img alt="GitHub Actions Workflow Status" src="https://img.shields.io/github/actions/workflow/status/gradion-ai/ipybox/test.yml"></a>
    <a href="https://github.com/gradion-ai/ipybox/blob/main/LICENSE"><img alt="GitHub License" src="https://img.shields.io/github/license/gradion-ai/ipybox?color=blueviolet"></a>
</p>

[ipybox](https://gradion-ai.github.io/ipybox/) is a local, sandboxed execution environment for running Python code, shell commands and programmatic MCP tool calls with a unified execution model.

ipybox executes Python code and shell commands in a stateful IPython kernel. Definitions and variables persist across executions, and kernels can be sandboxed with [sandbox-runtime](https://github.com/anthropic-experimental/sandbox-runtime), enforcing filesystem and network restrictions on OS-level.

It can generate Python APIs for MCP server tools via [mcpygen](https://gradion-ai.github.io/mcpygen/), and supports application-level approval of programmatic MCP tool calls and shell commands during execution. ipybox runs locally on your computer, enabling protected access to your local data and tools.

> [!NOTE]
> **Next generation ipybox**
>
> This is the next generation of ipybox, a complete rewrite. Older versions are maintained on the [0.6.x branch](https://github.com/gradion-ai/ipybox/tree/0.6.x) and can be obtained with `pip install ipybox<0.7`.

## Documentation:

- 📚 [Documentation](https://gradion-ai.github.io/ipybox/)
- 🏗️ [Architecture](https://gradion-ai.github.io/ipybox/architecture/)
- 🤖 [llms.txt](https://gradion-ai.github.io/ipybox/llms.txt)
- 🤖 [llms-full.txt](https://gradion-ai.github.io/ipybox/llms-full.txt)

## Capabilities

| Capability | Description |
| --- | --- |
| **Stateful code execution** | State persists across executions in IPython kernels |
| **Unified execution model** | Mix Python code, shell commands, and programmatic MCP tool calls in a single code block |
| **Shell command execution** | Run shell commands via `!cmd` syntax, capture output into Python variables |
| **Programmatic MCP tool calling** | MCP tools called via generated Python API, not JSON directly |
| **Python tool API generation** | Typed functions and Pydantic models generated from MCP tool schemas via [mcpygen](https://gradion-ai.github.io/mcpygen/) |
| **Application-level approval** | Optional approval of tool calls and shell commands before execution |
| **Lightweight sandboxing** | Optional kernel isolation via Anthropic's [sandbox-runtime](https://github.com/anthropic-experimental/sandbox-runtime) |
| **Local code execution** | No cloud dependencies, everything runs on your machine |

## Usage

| Component | Description |
| --- | --- |
| **[Python SDK](https://gradion-ai.github.io/ipybox/api/code_executor/)** | Python API for building applications on ipybox |
| **[MCP server](https://gradion-ai.github.io/ipybox/mcpserver/)** | ipybox as MCP server for code actions and programmatic tool calling |
| **[Claude Code plugin](https://gradion-ai.github.io/ipybox/ccplugin/)** | Plugin that bundles the ipybox MCP server and a code action skill |

> [!TIP]
> **freeact**
>
> [Freeact](https://github.com/gradion-ai/freeact) is an agent harness and CLI tool built on ipybox.
