# ipybox

Unified execution environment for Python code, shell commands, and programmatic MCP tool calls.

## Overview

ipybox executes code blocks in a stateful IPython kernel. A code block can contain any combination of Python code, shell commands, and programmatic MCP tool calls. Kernels can be sandboxed with [sandbox-runtime](https://github.com/anthropic-experimental/sandbox-runtime), enforcing filesystem and network restrictions at OS level.

It generates Python APIs for MCP server tools via [mcpygen](https://gradion-ai.github.io/mcpygen/), and supports application-level approval of individual tool calls and shell commands during code execution. ipybox runs locally on your computer, enabling protected access to your local data and tools.

## Capabilities

| Capability                      | Description                                                                                                              |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| **Stateful execution**          | Definitions and variables persist across executions in IPython kernels                                                   |
| **Unified execution**           | Combine Python code, shell commands, and programmatic MCP tool calls in a code block                                     |
| **Shell command execution**     | Run shell commands via `!cmd` syntax, capture output into Python variables                                               |
| **Programmatic MCP tool calls** | MCP tools called via generated Python APIs ("code mode"), not JSON directly                                              |
| **Python tool API generation**  | Typed functions and Pydantic models generated from MCP tool schemas via [mcpygen](https://gradion-ai.github.io/mcpygen/) |
| **Application-level approval**  | Individual approval of tool calls and shell commands during code execution                                               |
| **Lightweight sandboxing**      | Optional kernel isolation via Anthropic's [sandbox-runtime](https://github.com/anthropic-experimental/sandbox-runtime)   |
| **Local execution**             | No cloud dependencies, everything runs locally on your machine                                                           |

## Usage

| Component                                                                        | Description                                                         |
| -------------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| **[Python SDK](https://gradion-ai.github.io/ipybox/api/code_executor/index.md)** | Python API for building applications on ipybox                      |
| **[MCP server](https://gradion-ai.github.io/ipybox/mcpserver/index.md)**         | ipybox as MCP server for code actions and programmatic tool calling |
| **[Claude Code plugin](https://gradion-ai.github.io/ipybox/ccplugin/index.md)**  | Plugin that bundles the ipybox MCP server and a code action skill   |

Freeact agent

[Freeact](https://gradion-ai.github.io/freeact/) is a general-purpose agent built on ipybox.
