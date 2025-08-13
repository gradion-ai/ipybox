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
- `--allowed-domain`: Domain, IP address, or CIDR range allowed for outbound network access from container. Can be specified multiple times. See [Network Restrictions](#network-restrictions).
- `--container-tag`: Docker image to use (default: `ghcr.io/gradion-ai/ipybox:latest`)
- `--container-env-var`: Environment variable for container (format: `KEY=VALUE`). Can be specified multiple times.
- `--container-env-file`: Path to a file with environment variables for container
- `--container-bind`: Bind mount for container (format: `host_path:container_path`). Host paths may be relative or absolute. Container paths must be relative and are created as subdirectories of `/app`. Can be specified multiple times.

## Network Restrictions

By default, containers allow all outbound internet traffic. You can restrict network access by specifying allowed domains, IP addresses, or CIDR ranges using the `--allowed-domain` option:

```json
{
  "mcpServers": {
    "ipybox": {
      "command": "uvx",
      "args": [
        "ipybox",
        "mcp",
        "--allowed-domain", "gradion.ai",
        "--allowed-domain", "api.openai.com",
        "--allowed-domain", "192.168.1.0/24"
      ]
    }
  }
}
```

**Important Notes:**

- Network restrictions only work with non-root container images (images built without the `-r` or `--root` flag)
- If no `--allowed-domain` options are specified, the container runs without firewall restrictions
- For more details on network access control, see the [restrict network access](examples.md#restrict-network-access) section in the examples documentation

## Tools

The MCP server provides four tools:

- `execute_ipython_cell`: Executes Python code in a stateful IPython kernel. Variables, definitions and imports persist across executions.
- `upload_file`: Transfers files from host to container filesystem.
- `download_file`: Transfers files from container to host filesystem.
- `reset`: Creates a new IPython kernel, clearing all variables, definitions and imports while preserving installed packages and files.
