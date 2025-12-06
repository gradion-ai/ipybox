# Python Tool API Generation

```python
--8<-- "examples/apigen.py:imports"
```

`generate_mcp_sources()` generates a typed Python tool API from MCP server tool schemas. Each tool becomes a module with a Pydantic `Params` class, a `Result` class or `str` return type, and a `run()` function.

## Stdio servers

For MCP servers that run as local processes, specify `command`, `args`, and optional `env`:

```python
--8<-- "examples/apigen.py:gen_brave_search_wrappers"
```

## HTTP servers

For remote MCP servers over HTTP, specify `url` and optional `headers`:

```python
--8<-- "examples/apigen.py:gen_github_wrappers"
```

ipybox auto-detects the transport type from the URL. URLs containing `/mcp` use streamable HTTP, URLs containing `/sse` use SSE. You can also set `type` explicitly to `"streamable_http"` or `"sse"`.

## Environment variable substitution

Use `${VAR_NAME}` placeholders in `server_params` values. ipybox replaces them with the corresponding environment variable when connecting to the MCP server. This keeps secrets out of your code.

## Generated package structure

After generating the API for `brave_search` with `root_dir=Path("mcptools")`:

```
mcptools/
└── brave_search/
    ├── __init__.py
    ├── brave_web_search.py
    ├── brave_local_search.py
    ├── brave_image_search.py
    └── ...
```

## Using the generated API

Each tool module provides typed interfaces:

```python
from mcptools.brave_search.brave_image_search import Params, Result, run

# Params validates input
params = Params(query="neural topic models", count=3)

# run() calls the MCP tool and returns a Result (or str for untyped tools)
result: Result = run(params)

for image in result.items:
    print(image.title)
```

The `Params` class is generated from the tool's input schema. Tools with an output schema get a typed `Result` class; others return `str`.

## Next steps

- [Code Execution](codeexec.md) - Running code and handling tool approvals
- [Sandboxing](sandbox.md) - Secure execution with network and filesystem isolation
