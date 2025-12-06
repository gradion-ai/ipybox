# Docker

The ipybox MCP server can be run in a Docker container.

## Building the image

```bash
docker build -t ipybox .
```

## Running as MCP server

Configure your MCP client to use the container with stdio transport:

```json
{
  "mcpServers": {
    "ipybox": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "-v", "/path/to/workspace:/app/workspace",
        "ipybox"
      ]
    }
  }
}
```

The `-i` flag is required for stdio communication. The `--rm` flag removes the container after it exits.

## Configuration

The container uses fixed settings:

| Setting | Value |
|---------|-------|
| Workspace | `/app/workspace` |
| Tool Server Host | `localhost` |
| Tool Server Port | `8900` |
| Kernel Gateway Host | `localhost` |
| Kernel Gateway Port | `8888` |
| Log Level | `INFO` |

## Workspace

The workspace directory inside the container is `/app/workspace`. Mount your local workspace using a bind mount:

```bash
-v $(pwd)/my-workspace:/app/workspace
```

Files created by the MCP server (e.g., generated images, MCP tool packages) will be written to this directory.

## Environment variables

Environment variables prefixed with `KERNEL_ENV_` are passed to the IPython kernel (with the prefix stripped). For example:

```json
{
  "mcpServers": {
    "ipybox": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "-e", "KERNEL_ENV_API_KEY=secret",
        "-v", "/path/to/workspace:/app/workspace",
        "ipybox"
      ]
    }
  }
}
```

This makes `API_KEY=secret` available inside the kernel environment.
