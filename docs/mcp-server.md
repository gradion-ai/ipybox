# MCP Server

`ipybox` can be configured as an [MCP](https://modelcontextprotocol.io/) server providing secure Python code execution in Docker containers with a stateful IPython kernel. The kernel maintains execution state across code executions until explicitly reset. Files can be uploaded to and downloaded from the container. Host filesystem operations are restricted to whitelisted directories for security.

## Configuration

### Minimal Configuration

```json
{
  "mcpServers": {
    "ipybox": {
      "command": "uvx",
      "args": ["ipybox", "mcp"]
    }
  }
}
```

### Full Configuration

All available command-line options for advanced configuration:

```json
{
  "mcpServers": {
    "ipybox": {
      "command": "uvx",
      "args": [
        "ipybox",
        "mcp",
        "--allowed-dir", "/home/alice/projects",
        "--allowed-dir", "/tmp/data",
        "--container-tag", "ghcr.io/gradion-ai/ipybox:latest",
        "--container-env-var", "API_KEY=secret123",
        "--container-env-var", "DEBUG=true",
        "--container-env-file", "/home/alice/projects/agent/.env",
        "--container-bind", "/home/alice/datasets:datasets",
        "--container-bind", "/home/alice/models:models"
      ]
    }
  }
}
```

**Command-line options:**

- `--allowed-dir`: Directory allowed for host filesystem operations (default: home directory and `/tmp`). Can be specified multiple times.
- `--container-tag`: Docker image to use (default: `ghcr.io/gradion-ai/ipybox:latest`)
- `--container-env-var`: Environment variable for container (format: `KEY=VALUE`). Can be specified multiple times.
- `--container-env-file`: Path to a file with environment variables for container
- `--container-bind`: Bind mount for container (format: `host_path:container_path`). Host paths may be relative or absolute. Container paths must be relative and are created as subdirectories of `/app`. Can be specified multiple times.

## Tools

The MCP server provides four tools:

- `execute_ipython_cell`: Executes Python code in a stateful IPython kernel. Variables, definitions and imports persist across executions.
- `upload_file`: Transfers files from host to container filesystem.
- `download_file`: Transfers files from container to host filesystem.
- `reset`: Creates a new IPython kernel, clearing all variables, definitions and imports while preserving installed packages and files.
