import shutil
from pathlib import Path

import pytest

from ipybox import ExecutionClient, ResourceClient
from tests.mcp_server import MCP_SERVER_PATH


@pytest.mark.asyncio
async def test_get_module_source(resource_client: ResourceClient):
    # Get the source through the resource server
    result = await resource_client.get_module_sources(["ipybox.modinfo"])
    source = result["ipybox.modinfo"]

    # Load the actual source file
    modinfo_path = Path("ipybox", "modinfo.py")
    with open(modinfo_path) as f:
        actual_source = f.read()

    assert source == actual_source


@pytest.mark.asyncio
async def test_generate_and_get_mcp_sources(
    resource_client: ResourceClient, execution_client: ExecutionClient, workspace: str
):
    # Copy MCP server to /app/workspace/mcp_server.py into the container
    shutil.copy(MCP_SERVER_PATH, Path(workspace) / "mcp_server.py")

    server_params = {
        "command": "python",
        "args": ["workspace/mcp_server.py"],
    }

    # generate MCP client sources in /app/mcpgen/test
    gen_result = await resource_client.generate_mcp_sources(
        relpath="mcpgen", server_name="test", server_params=server_params
    )
    assert gen_result == ["tool_1", "tool_2"]

    # retrieve the generated sources via ipybox filesystem
    get_result_1 = await resource_client.get_mcp_sources(relpath="mcpgen", server_name="test")

    module_name_1 = "mcpgen.test.tool_1"
    module_name_2 = "mcpgen.test.tool_2"

    # get the generated sources via ipybox module loading
    get_result_2 = await resource_client.get_module_sources([module_name_1, module_name_2])

    source_1 = get_result_1["tool_1"]
    source_2 = get_result_1["tool_2"]

    # check if retrieval mechanisms are equivalent
    assert source_1 == get_result_2[module_name_1]
    assert source_2 == get_result_2[module_name_2]

    # check if it contains the generated function signature
    assert "tool_1(params: Params)" in source_1
    assert "tool_2(params: Params)" in source_2
