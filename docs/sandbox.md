# Sandboxing

ipybox uses [sandbox-runtime](https://github.com/anthropic-experimental/sandbox-runtime) to isolate code execution. When enabled, the IPython kernel runs with restricted filesystem and network access.

```python
--8<-- "examples/sandbox.py:imports"
```

## Default sandbox

Enable sandboxing with `sandbox=True`. The [default configuration](https://github.com/gradion-ai/ipybox/blob/main/ipybox/kernel_mgr/sandbox.json) blocks all internet access:

```python
--8<-- "examples/sandbox.py:default_sandbox"
```

## Custom sandbox config

Provide a JSON configuration file to customize restrictions:

```python
--8<-- "examples/sandbox.py:custom_sandbox"
```

See the [sandbox-runtime documentation](https://github.com/anthropics/sandbox-runtime) for all configuration options.

## Sandboxed MCP servers

MCP servers can also run in a sandbox using the `srt` wrapper. This provides layered security: the kernel sandbox and MCP server sandbox are independent.

```python
--8<-- "examples/sandbox.py:sandboxed_mcp_server"
```

In this example, the filesystem MCP server can access all files in the current directory, except that the sandbox blocks read access to `.env`. Even if the `server-filesystem` MCP server `server_params` allow full access to the current working directory, the sandbox enforces the restriction.

The MCP server sandbox config needs to allow access to its runtime dependencies (e.g., `registry.npmjs.org` for downloading the server package via `npx`, and `~/.npm` for npm cache).
