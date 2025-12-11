# ipybox

mcp-name: io.github.gradion-ai/ipybox

<p align="left">
    <a href="https://gradion-ai.github.io/ipybox/"><img alt="Website" src="https://img.shields.io/website?url=https%3A%2F%2Fgradion-ai.github.io%2Fipybox%2F&up_message=online&down_message=offline&label=docs"></a>
    <a href="https://pypi.org/project/ipybox/"><img alt="PyPI - Version" src="https://img.shields.io/pypi/v/ipybox?color=blue"></a>
    <a href="https://github.com/gradion-ai/ipybox/releases"><img alt="GitHub Release" src="https://img.shields.io/github/v/release/gradion-ai/ipybox"></a>
    <a href="https://github.com/gradion-ai/ipybox/actions"><img alt="GitHub Actions Workflow Status" src="https://img.shields.io/github/actions/workflow/status/gradion-ai/ipybox/test.yml"></a>
    <a href="https://github.com/gradion-ai/ipybox/blob/main/LICENSE"><img alt="GitHub License" src="https://img.shields.io/github/license/gradion-ai/ipybox?color=blueviolet"></a>
</p>

> [!NOTE]
> **Next generation ipybox**
>
> This is the next generation of ipybox, a complete rewrite. Older versions are maintained on the [0.6.x branch](https://github.com/gradion-ai/ipybox/tree/0.6.x) and can be obtained with `pip install ipybox<0.7`.

[ipybox](https://gradion-ai.github.io/ipybox/) is a Python code execution sandbox with first-class support for programmatic MCP tool calling. It generates a typed Python tool API from MCP server tool schemas, supporting both local stdio and remote HTTP servers. Code that calls the generated API executes in a sandboxed IPython kernel, providing a stateful environment where variables and definitions persist across executions. The generated API delegates MCP tool execution to a separate environment that enforces tool call approval, requiring applications to explicitly accept or reject each tool call before it executes.

![Architecture](docs/images/architecture-light-annotated.jpg)

*`CodeExecutor` coordinates sandboxed code execution, tool execution, and tool call approval.*

## Agent integration

ipybox is designed for agents that interact with their environment through [code actions](https://arxiv.org/abs/2402.01030) rather than JSON tool calls, a more reliable approach since LLMs are heavily pretrained on Python code compared to JSON tool call post-training. Agents generate and execute Python code that composes multiple MCP tool calls into a single action, using loops, conditionals, and data transformations that keep intermediate results out of the agent's context window. Since agent-generated code cannot be trusted, it must run in a secure sandboxed environment, and all MCP tool calls must be approved by the application. ipybox supports both with minimal setup.

## Features

- **Stateful code execution** — state persists across executions in IPython kernels
- **Lightweight sandboxing** — kernel isolation via Anthropic's [sandbox-runtime](https://github.com/anthropic-experimental/sandbox-runtime)
- **Generated Python tool API** — functions and models generated from MCP tool schemas
- **Programmatic MCP tool calling** — MCP tools called via Python code, not JSON directly
- **MCP tool call approval** — every MCP tool call requires application-level approval
- **Any MCP server** — supports stdio, Streamable HTTP, and SSE transports
- **Any Python package** — install and use any Python package in IPython kernels
- **Local code execution** — no cloud dependencies, everything runs on your machine
- **Python SDK and MCP server** — use ipybox programmatically or as an MCP server
- **Claude Code plugin** — a plugin for [programmatic tool calling in Claude Code](https://gradion-ai.github.io/ipybox/ccplugin/)

## Documentation

See the [documentation](https://gradion-ai.github.io/ipybox/) for installation instructions, quickstart guide, and detailed usage information. For LLM-friendly documentation, see [llms.txt](https://gradion-ai.github.io/ipybox/llms.txt) and [llms-full.txt](https://gradion-ai.github.io/ipybox/llms-full.txt).
