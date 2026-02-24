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

[ipybox](https://gradion-ai.github.io/ipybox/) is a Python code execution sandbox with first-class support for programmatic MCP tool calling. It generates typed Python tool APIs from MCP server tool schemas, supporting both local stdio and remote HTTP servers.

Code that calls the generated API executes in a sandboxed IPython kernel. The API delegates MCP tool execution to a separate environment that enforces tool call approval, requiring applications to accept or reject each tool call.

![Architecture](docs/images/architecture-dark.png)

*`CodeExecutor` coordinates sandboxed code execution, tool execution, and tool call approval.*

## Documentation:

- 📚 [Documentation](https://gradion-ai.github.io/ipybox/)
- 🤖 [llms.txt](https://gradion-ai.github.io/ipybox/llms.txt)
- 🤖 [llms-full.txt](https://gradion-ai.github.io/ipybox/llms-full.txt)

> [!NOTE]
> **Next generation ipybox**
>
> This is the next generation of ipybox, a complete rewrite. Older versions are maintained on the [0.6.x branch](https://github.com/gradion-ai/ipybox/tree/0.6.x) and can be obtained with `pip install ipybox<0.7`.

## Agent integration

ipybox is designed for agents that act by executing Python code rather than issuing JSON tool calls. This [code action](https://arxiv.org/abs/2402.01030) approach enables tool composition and intermediate result processing in a single inference pass, keeping intermediate results out of the agent's context window.

Code actions are also key for agents to improve themselves and their tool libraries by capturing successful experience as executable knowledge. Agent-generated code cannot be trusted and requires sandboxed execution with application-level approval for every MCP tool call.

> [!TIP]
> **freeact**
>
> A code action agent built on ipybox is [freeact](https://github.com/gradion-ai/freeact). In addition to inheriting the [capabilities](#capabilities) of ipybox, it supports progressive loading of tools and [agent skills](https://agentskills.io), and can save successful code actions as tools, evolving its own tool library over time.

## Capabilities

| Capability | Description |
| --- | --- |
| **Stateful code execution** | State persists across executions in IPython kernels |
| **Lightweight sandboxing** | Kernel isolation via Anthropic's [sandbox-runtime](https://github.com/anthropic-experimental/sandbox-runtime) |
| **Programmatic MCP tool calling** | MCP tools called via Python code, not JSON directly |
| **MCP tool call approval** | Every MCP tool call requires application-level approval |
| **Python tool API generation** | Functions and models generated from MCP tool schemas |
| **Any MCP server** | Supports stdio, Streamable HTTP, and SSE transports |
| **Any Python package** | Install and use any Python package in IPython kernels |
| **Local code execution** | No cloud dependencies, everything runs on your machine |

## Usage

| Component | Description |
| --- | --- |
| **[Python SDK](https://gradion-ai.github.io/ipybox/api/code_executor/)** | Python API for building applications on ipybox |
| **[MCP server](https://gradion-ai.github.io/ipybox/mcpserver/)** | ipybox as MCP server for code actions and programmatic tool calling |
| **[Claude Code plugin](https://gradion-ai.github.io/ipybox/ccplugin/)** | Plugin that bundles the ipybox MCP server and a code action skill |
