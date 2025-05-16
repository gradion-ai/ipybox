import shutil
from pathlib import Path

import pytest

from ipybox import ExecutionClient, ResourceClient


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
async def test_mcp(resource_client: ResourceClient, execution_client: ExecutionClient, workspace: str):
    # Copy MCP server to /app/workspace/mcp_server.py into the container
    mcp_server_path = Path(__file__).parent / "mcp_server.py"
    shutil.copy(mcp_server_path, Path(workspace) / "mcp_server.py")

    server_params = {
        "command": "python",
        "args": ["workspace/mcp_server.py"],
    }

    # generate MCP client sources in /app/mcpgen/test
    gen_result = await resource_client.generate_mcp_sources(
        relpath="mcpgen", server_name="test", server_params=server_params
    )
    assert gen_result == ["get_weather"]

    # retrieve the generated sources via ipybox filesystem
    get_result_1 = await resource_client.get_mcp_sources(relpath="mcpgen", server_name="test")
    source_1 = get_result_1["get_weather"]

    module_name = "mcpgen.test.get_weather"

    # get the generated sources via ipybox module loading
    get_result_2 = await resource_client.get_module_sources([module_name])

    # check if retrieval mechanisms are equivalent
    assert get_result_1["get_weather"] == get_result_2[module_name]

    # check if it contains the generated function signature
    assert "get_weather(params: Params)" in source_1

    # Execute the MCP server via the generated function
    exec_result = await execution_client.execute("""
from mcpgen.test.get_weather import get_weather, Params
print(get_weather(Params(city="Graz")))
""")
    assert exec_result.text == "The weather in Graz is sunny"
