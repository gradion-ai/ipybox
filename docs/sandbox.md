# Sandboxing

ipybox uses Anthropic's [sandbox-runtime](https://github.com/anthropic-experimental/sandbox-runtime) to isolate code execution. When enabled, the IPython kernel runs with restricted filesystem and network access.

```python
--8<-- "examples/sandbox.py:imports"
```

## Default sandbox

Enable sandboxing with `sandbox=True`.

```python
--8<-- "examples/sandbox.py:default_sandbox"
```

The default sandbox configuration allows:

- Reading all files except `.env`
- Writing to the current directory and subdirectories (plus IPython directories)
- Local network access to the tool execution server

```json title="Default sandbox configuration"
--8<-- "ipybox/kernel_mgr/sandbox.json"
```

Internet access is blocked as demonstrated in the example above. See the [sandbox-runtime](https://github.com/anthropic-experimental/sandbox-runtime) documentation for all configuration options.

## Custom sandbox

To allow access to `example.org`, provide a custom sandbox configuration file:

```json title="examples/sandbox-kernel.json"
--8<-- "examples/sandbox-kernel.json"
```

and pass it as `sandbox_config` argument:

```python
--8<-- "examples/sandbox.py:custom_sandbox"
```

## Sandboxing MCP servers

stdio MCP servers like the [filesystem MCP server](https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem) can be configured to run in a sandbox using `srt` as command:

```python
--8<-- "examples/sandbox.py:sandboxed_mcp_server_params"
```

The sandbox configuration is:

```json title="examples/sandbox-mcp.json"
--8<-- "examples/sandbox-mcp.json"
```

The server itself is configured with permissions to access all files in the current directory (`"."`), but the sandbox additionally blocks read access to `.env`. The sandbox also allows access to `registry.npmjs.org` for downloading the server package via `npx`, and `~/.npm` for the local `npm` cache.

```python
--8<-- "examples/sandbox.py:sandboxed_mcp_server_usage"
```

!!! Info

    MCP server sandboxing is independent of kernel sandboxing and usually not needed when using trusted servers, but provides an additional security layer when needed. 
