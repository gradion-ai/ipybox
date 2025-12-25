# Sandboxing

ipybox uses Anthropic's [sandbox-runtime](https://github.com/anthropic-experimental/sandbox-runtime) to isolate code execution. When enabled, the IPython kernel runs with restricted filesystem and network access.

```
from ipybox import CodeExecutionError, CodeExecutor, generate_mcp_sources
```

## Default sandbox

Enable sandboxing with `sandbox=True`.

```
async with CodeExecutor(sandbox=True) as executor:
    result = await executor.execute("print('hello world')")
    assert result.text == "hello world"

    code = """
    import requests
    try:
        requests.get('https://example.org')
    except Exception as e:
        print(e)
    """

    # Default sandbox config blocks internet access
    result = await executor.execute(code)
    assert "Failed to resolve 'example.org'" in result.text
```

The default sandbox configuration allows:

- Reading all files except `.env`
- Writing to the current directory and subdirectories (plus IPython directories)
- Local network access to the tool execution server

Default sandbox configuration

```
{
  "enableWeakerNestedSandbox": false,
  "filesystem": {
    "denyRead": [".env"],
    "allowWrite": [".", "~/Library/Jupyter", "~/.ipython"],
    "denyWrite": []
  },
  "network": {
    "allowedDomains": [],
    "deniedDomains": [],
    "allowLocalBinding": true
  }
}
```

Internet access is blocked as demonstrated in the example above. See the [sandbox-runtime](https://github.com/anthropic-experimental/sandbox-runtime) documentation for all configuration options.

## Custom sandbox

To allow access to `example.org`, provide a custom sandbox configuration file:

examples/sandbox-kernel.json

```
{
    "enableWeakerNestedSandbox": false,
    "filesystem": {
      "denyRead": [".env"],
      "allowWrite": [".", "~/Library/Jupyter", "~/.ipython"],
      "denyWrite": []
    },
    "network": {
      "allowedDomains": ["example.org"],
      "deniedDomains": [],
      "allowLocalBinding": true
    }
  }
```

and pass it as `sandbox_config` argument:

```
code = """
import requests
result = requests.get('https://example.org')
print(result.text)
"""
async with CodeExecutor(
    sandbox=True,
    sandbox_config=Path("examples/sandbox-kernel.json"),
    log_level="WARNING",
) as executor:
    result = await executor.execute(code)
    assert "Example Domain" in result.text
```

## Sandboxing MCP servers

### Filesystem MCP server

stdio MCP servers like the [filesystem MCP server](https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem) can be configured to run in a sandbox using `srt` as command:

```
server_params = {
    "command": "srt",
    "args": [
        "--settings",
        "examples/sandbox-filesystem-mcp.json",
        "npx",
        "-y",
        "@modelcontextprotocol/server-filesystem",
        ".",
    ],
}
```

The sandbox configuration is:

examples/sandbox-filesystem-mcp.json

```
{
    "enableWeakerNestedSandbox": false,
    "filesystem": {
      "denyRead": [".env"],
      "allowWrite": [".", "~/.npm"],
      "denyWrite": []
    },
    "network": {
      "allowedDomains": ["registry.npmjs.org"],
      "deniedDomains": [],
      "allowLocalBinding": true
    }
  }
```

The server itself is configured with permissions to access all files in the current directory (`"."`), but the sandbox additionally blocks read access to `.env`. The sandbox also allows access to `registry.npmjs.org` for downloading the server package via `npx`, and `~/.npm` for the local `npm` cache.

```
await generate_mcp_sources("filesystem", server_params, Path("mcptools"))

list_dir_code = """
from mcptools.filesystem.list_directory import run, Params
result = run(Params(path="."))
print(result.content)
"""

read_env_code = """
from mcptools.filesystem.read_file import run, Params
result = run(Params(path=".env"))
print(result.content)
"""

async with CodeExecutor(sandbox=True) as executor:
    # allowed by MCP server and sandbox
    result = await executor.execute(list_dir_code)
    assert "README.md" in result.text

    try:
        # allowed by MCP server but blocked by sandbox
        result = await executor.execute(read_env_code)
        assert False, "Read access to .env not blocked"
    except CodeExecutionError as e:
        assert "operation not permitted" in str(e)
```

Info

MCP server sandboxing is independent of kernel sandboxing and usually not needed when using trusted servers, but provides an additional security layer when needed.

### Fetch MCP server

The [fetch MCP server](https://github.com/modelcontextprotocol/servers/tree/main/src/fetch) retrieves web content and converts it to markdown. Install the server and SOCKS proxy support (used by sandbox-runtime for network filtering) as project dependencies:

```
uv add mcp-server-fetch
uv add "httpx[socks]>=0.28.1"
```

Note

Running via `uvx` is currently not supported because `srt` restricts access to system configuration required by `uvx`.

Configure the server to run in a sandbox using `python -m mcp_server_fetch`:

```
server_params = {
    "command": "srt",
    "args": [
        "--settings",
        "examples/sandbox-fetch-mcp.json",
        "python",
        "-m",
        "mcp_server_fetch",
    ],
}
```

The sandbox configuration allows access to `example.com` for fetching content and `registry.npmjs.org` for the [readability](https://github.com/mozilla/readability) dependency:

examples/sandbox-fetch-mcp.json

```
{
  "enableWeakerNestedSandbox": false,
  "filesystem": {
    "denyRead": [".env"],
    "allowWrite": [".", "~/.npm", "/tmp/**", "/private/tmp/**"],
    "denyWrite": []
  },
  "network": {
    "allowedDomains": ["registry.npmjs.org", "example.com"],
    "deniedDomains": [],
    "allowLocalBinding": true
  }
}
```

```
await generate_mcp_sources("fetch", server_params, Path("mcptools"))

fetch_code = """
from mcptools.fetch import fetch
result = fetch.run(fetch.Params(url="https://example.com"))
print(result)
"""

async with CodeExecutor(sandbox=True) as executor:
    result = await executor.execute(fetch_code)
    print(result.text)
    assert "This domain is for use in documentation examples" in result.text
```
