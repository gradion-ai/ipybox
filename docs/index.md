# ipybox

ipybox is a Python code execution sandbox with first-class support for programmatic MCP tool use. It generates typed Python wrapper functions from MCP server tool schemas, supporting both local stdio and remote HTTP servers. Code that calls these generated functions executes in a sandboxed IPython kernel, providing a stateful environment where variables and definitions persist across executions. Generated wrapper functions delegate MCP tool execution to a separate environment that enforces tool call approval, requiring applications to explicitly accept or reject each tool call before it executes.

ipybox is designed for agents that interact with their environment through code actions rather than JSON tool calls, a more reliable approach since LLMs are heavily pretrained on Python code compared to JSON tool call post-training. Agents generate and execute Python code that composes multiple MCP tool calls into a single action, using loops, conditionals, and data transformations that keep intermediate results out of the agent's context window. Since agent-generated code cannot be trusted, it must run in a secure sandboxed environment, and all MCP tool calls must be approved by the application. ipybox supports both with minimal setup.

<figure markdown>
  ![Architecture](images/architecture-light.png#only-light){ width="80%" }
  ![Architecture](images/architecture-light.png#only-dark){ width="80%" }
  <figcaption>ipybox executes code in a sandboxed IPython kernel where state persists across executions. Python tool wrappers called from executed code delegate MCP tool execution to a separate tool executor, which enforces approval before forwarding a call to an MCP server.</figcaption>
</figure>

## Features

- **Python API and MCP server** — use ipybox programmatically or as an MCP server for agents
- **Programmatic MCP tool use** — call MCP tools from Python code instead of JSON tool calls
- **Generated tool wrappers** — typed Python functions generated from MCP server schemas
- **Stateful code execution** — variables and definitions persist across executions in IPython kernels
- **Lightweight sandboxing** — kernel isolation via Anthropic's sandbox-runtime
- **MCP tool call approval** — every tool call requires application-level approval
- **Any MCP server** — supports stdio, Streamable HTTP, and SSE transports
- **Any Python package** — install and use any package in IPython kernels
- **Local code execution** — no cloud dependencies required
- **Claude Code plugin** — code action plugin i.e. "code-mode" for Claude Code
