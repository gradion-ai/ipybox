# ipybox

ipybox is a Python code execution sandbox with first-class support for programmatic MCP tool use. It generates typed Python wrapper functions from MCP server tool schemas, supporting both local stdio and remote HTTP servers. Code that calls these generated functions executes in a sandboxed IPython kernel, providing a stateful environment where variables and definitions persist across executions. Generated wrapper functions delegate MCP tool execution to a separate environment that enforces tool call approval, requiring applications to explicitly accept or reject each tool call before it executes.

ipybox is designed for agents that interact with their environment through code actions rather than JSON tool calls, a more reliable approach since LLMs are heavily pretrained on Python code compared to JSON tool call post-training. Agents generate and execute Python code that composes multiple MCP tool calls into a single action, using loops, conditionals, and data transformations that keep intermediate results out of the agent's context window. Since agent-generated code cannot be trusted, it must run in a secure sandboxed environment, and all MCP tool calls must be approved by the application. ipybox supports both with minimal setup.

## Interfaces

- Python API
- MCP server

## Features

- Python code execution in sandboxed IPython kernels
- Programmatic MCP tool use based on generated Python wrapper functions
- Supports MCP servers with stdio, http and sse transports
- Tool call approval that cannot be bypassed by executing code
- ...

## Additional features

- any python package can be installed and used in IPython kernels
- fully local code execution in IPython kernels, no cloud dependencies
- supports any MCP server for programmatic tool use
- sandboxing based on Anthropic's sandbox-runtime (`srt`)
- configurable sandboxing of IPython kernels, turned off by default
- optional, application-level sandboxing of MCP servers (via `srt`)
- ipybox MCP server can also be run as a Docker container
- support for plotting figures with matplotlib and other libraries

## Current limitations

- srt sandboxing not working yet on Linux, but runs without sandboxing
- OAuth workflow for MCP servers not supported yet
- only text returned by MCP servers is processed, media not yet
