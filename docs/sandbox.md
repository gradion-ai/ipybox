# Sandboxing

ipybox uses Anthropic's [sandbox-runtime](https://github.com/anthropic-experimental/sandbox-runtime) to isolate code execution. When enabled, the IPython kernel runs with restricted filesystem and network access.

```python
--8<-- "examples/sandbox.py:imports"
```

## Default sandbox

Enable sandboxing with `sandbox=True`. The [default configuration](https://github.com/gradion-ai/ipybox/blob/main/ipybox/kernel_mgr/sandbox.json) permits:

- Reading all files except `.env`
- Writing to the current directory and subdirectories (plus IPython directories)
- Local access to the tool execution server but internet access is blocked

```python
--8<-- "examples/sandbox.py:default_sandbox"
```

## Custom sandbox

Provide a JSON configuration file to customize restrictions. The example below fetches content from `example.org`, which would fail with the default config:

```python
--8<-- "examples/sandbox.py:custom_sandbox"
```

The [custom config](https://github.com/gradion-ai/ipybox/blob/main/examples/sandbox-kernel.json) adds `example.org` to `allowedDomains`, permitting network access to that domain while keeping all other restrictions from the default. See the [sandbox-runtime](https://github.com/anthropic-experimental/sandbox-runtime) documentation for all configuration options.

## Sandboxing MCP servers

stdio MCP servers can also run in a sandbox using `srt` as command. MCP server sandboxing is independent of kernel sandboxing and usually not needed when using trusted servers, but provides an additional security layer when needed. The example below uses a [custom MCP server sandbox config](https://github.com/gradion-ai/ipybox/blob/main/examples/sandbox-mcp.json):

```python
--8<-- "examples/sandbox.py:sandboxed_mcp_server"
```

The filesystem MCP server is configured with permissions to access all files in the current directory (`"."`), but the sandbox additionally blocks read access to `.env`. The sandbox also allows access to `registry.npmjs.org` for downloading the server package via `npx`, and `~/.npm` for the local npm cache.
