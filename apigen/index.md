# Python tool API generation

```python
from ipybox import generate_mcp_sources
```

generate_mcp_sources() generates a typed Python tool API from MCP server tool schemas. Each tool becomes a module with a Pydantic `Params` class, a `Result` class or `str` return type, and a `run()` function.

## Stdio servers

For MCP servers that run as local processes, specify `command`, `args`, and optional `env`:

```python
brave_mcp_params = {
    "command": "npx",
    "args": ["-y", "@brave/brave-search-mcp-server", "--transport", "stdio"],
    "env": {"BRAVE_API_KEY": "${BRAVE_API_KEY}"},
}

await generate_mcp_sources(
    server_name="brave_search",
    server_params=brave_mcp_params,
    root_dir=Path("mcptools"),
)
```

## HTTP servers

For remote MCP servers over HTTP, specify `url` and optional `headers`:

```python
github_mcp_params = {
    "url": "https://api.githubcopilot.com/mcp/",
    "headers": {"Authorization": "Bearer ${GITHUB_API_KEY}"},
}

await generate_mcp_sources(
    server_name="github",
    server_params=github_mcp_params,
    root_dir=Path("mcptools"),
)
```

ipybox auto-detects the transport type from the URL. URLs containing `/mcp` use streamable HTTP, URLs containing `/sse` use SSE. You can also set `type` explicitly to `"streamable_http"` or `"sse"`.

## Environment variable substitution

You can use `${VAR_NAME}` placeholders in `server_params` values. ipybox replaces them with the corresponding environment variable when connecting to the MCP server. This keeps secrets out of your code.

## Generated package structure

The Brave Search MCP server [example above](#stdio-servers) generates a package structure like this:

```text
mcptools/
└── brave_search/
    ├── __init__.py
    ├── brave_web_search.py
    ├── brave_local_search.py
    ├── brave_image_search.py
    └── ...
```

For each MCP server tool, a separate Python module is generated, named after the tool.

## Using the generated API

Each module provides a typed interface for programmatic MCP tool calls:

```python
from mcptools.brave_search.brave_image_search import Params, Result, run

# Params validates input
params = Params(query="neural topic models", count=3)

# run() calls the MCP tool and returns a Result (or str for untyped tools)
result: Result = run(params)

for image in result.items:
    print(image.title)
```

The `Params` class is generated from the tool's input schema. Tools with an output schema get a typed `Result` class; others return `str`. The MCP tool itself is called via its `run()` function.
