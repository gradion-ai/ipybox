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

[ipybox](https://gradion-ai.github.io/ipybox/) is a unified execution environment for Python code, shell commands, and programmatic MCP tool calls.

## Overview

ipybox executes code blocks in a stateful IPython kernel. A code block can contain any combination of Python code, shell commands, and programmatic MCP tool calls. Kernels can be sandboxed with [sandbox-runtime](https://github.com/anthropic-experimental/sandbox-runtime), enforcing filesystem and network restrictions at OS level.

It generates Python APIs for MCP server tools via [mcpygen](https://gradion-ai.github.io/mcpygen/), and supports application-level approval of individual tool calls and shell commands during code execution. ipybox runs locally on your computer, enabling protected access to your local data and tools.

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
| **Stateful execution** | State persists across executions in IPython kernels |
| **Unified execution** | Combine Python code, shell commands, and programmatic MCP tool calls in a code block |
| **Shell command execution** | Run shell commands via `!cmd` syntax, capture output into Python variables |
| **Programmatic MCP tool calls** | MCP tools called via generated Python API ("code mode"), not JSON directly |
| **Python tool API generation** | Typed functions and Pydantic models generated from MCP tool schemas via [mcpygen](https://gradion-ai.github.io/mcpygen/) |
| **Application-level approval** | Individual approval of tool calls and shell commands during code execution |
| **Lightweight sandboxing** | Optional kernel isolation via Anthropic's [sandbox-runtime](https://github.com/anthropic-experimental/sandbox-runtime) |
| **Local execution** | No cloud dependencies, everything runs locally on your machine |

## Usage

| Component | Description |
| --- | --- |
| **[Python SDK](https://gradion-ai.github.io/ipybox/api/code_executor/)** | Python API for building applications on ipybox |
| **[MCP server](https://gradion-ai.github.io/ipybox/mcpserver/)** | ipybox as MCP server for code actions and programmatic tool calling |
| **[Claude Code plugin](https://gradion-ai.github.io/ipybox/ccplugin/)** | Plugin that bundles the ipybox MCP server and a code action skill |

> [!TIP]
> **Freeact agent**
>
> [Freeact](https://github.com/gradion-ai/freeact) is a general-purpose agent built on ipybox.
