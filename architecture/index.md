# Architecture

`CodeExecutor` coordinates three components: a Jupyter kernel for stateful Python execution, a tool server for MCP tool dispatch, and an approval channel for application-level tool call control.

The application submits code to `CodeExecutor`, which forwards it to an IPython kernel running inside an optional sandbox. When that code calls a generated Python tool API function, the request routes to the tool server, which manages local (stdio) and remote (HTTP) MCP servers.

Before executing any tool call, the tool server sends an approval request back through `CodeExecutor` to the application, blocking until it accepts or rejects. This separates code execution from tool execution, enforcing independent security boundaries: the kernel is network-isolated from MCP servers, and every tool call passes through the approval layer.

`CodeExecutor` coordinates sandboxed code execution, tool execution, and tool call approval.
