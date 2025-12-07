import os

from ipybox.tool_exec.client import ToolRunner

CLIENT = ToolRunner(
    server_name="github",
    server_params={
        "url": "https://api.githubcopilot.com/mcp/",
        "headers": {"Authorization": "Bearer ${GITHUB_API_KEY}"},
    },
    host=os.environ.get("TOOL_SERVER_HOST", "localhost"),
    port=int(os.environ.get("TOOL_SERVER_PORT", "8900")),
)
