import tempfile
from pathlib import Path

import pytest
from mcp import ClientSession

from ipybox.mcp.gen import (
    generate_function_definition,
    generate_init_definition,
    generate_input_definition,
    generate_mcp_sources,
    sanitize_name,
)
from ipybox.mcp.run import mcp_client, run_async

# Test constants
TOOL1_NAME = "tool-1"
TOOL2_NAME = "tool_2"
NONEXISTENT_TOOL = "non_existent_tool"
TEST_SERVER_NAME = "test_mcp_server"


@pytest.fixture
def temp_dir():
    """Create a temporary directory for the tests."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.mark.parametrize(
    "input_name,expected",
    [
        (TOOL1_NAME, "tool_1"),
        (TOOL2_NAME, TOOL2_NAME),
        ("Tool_3", "tool_3"),
        ("tool with spaces", "tool_with_spaces"),
    ],
)
def test_sanitize_name(input_name, expected):
    """Test the sanitize_name function."""
    assert sanitize_name(input_name) == expected


def test_generate_init_definition(server_params):
    """Test the generate_init_definition function."""
    init_content = generate_init_definition(server_params)

    # Check that the required elements are in the init content
    assert "SERVER_PARAMS = " in init_content

    # Check for stdio transport parameters
    if "command" in server_params:
        assert f"'command': '{server_params['command']}'" in init_content
        assert f"'args': {server_params['args']}" in init_content

    # Check for HTTP/SSE transport parameters
    if "url" in server_params:
        assert f"'url': '{server_params['url']}'" in init_content
        assert f"'type': '{server_params['type']}'" in init_content


@pytest.mark.parametrize(
    "sanitized_name,original_name,description,expected_fragments",
    [
        (
            "tool_1",
            TOOL1_NAME,
            "This is tool 1.",
            ["def tool_1(params: Params) -> str:", "This is tool 1.", f'run_sync("{TOOL1_NAME}"'],
        ),
        (
            "tool_with_quotes",
            "tool_with_quotes",
            'This contains """triple quotes""".',
            [
                "def tool_with_quotes(params: Params) -> str:",
                r"This contains \"\"\"triple quotes\"\"\".",
                'run_sync("tool_with_quotes"',
            ],
        ),
    ],
)
def test_generate_function_definition(sanitized_name, original_name, description, expected_fragments):
    """Test the generate_function_definition function."""
    function_def = generate_function_definition(sanitized_name, original_name, description)

    # Check that the function definition contains the correct elements
    for fragment in expected_fragments:
        assert fragment in function_def


def test_generate_input_definition():
    """Test the generate_input_definition function."""
    # Create a simple schema similar to what FastMCP would generate for tool_1
    schema = {"type": "object", "properties": {"s": {"type": "string"}}, "required": ["s"]}

    input_def = generate_input_definition(schema)

    # Check that the input definition contains a Pydantic model
    assert "class Params(" in input_def
    assert "s: str" in input_def

    # Test with a more complex schema
    complex_schema = {
        "type": "object",
        "properties": {"s": {"type": "string"}, "n": {"type": "number"}, "b": {"type": "boolean"}},
        "required": ["s", "n"],
    }

    complex_input_def = generate_input_definition(complex_schema)
    assert "class Params(" in complex_input_def
    assert "s: str" in complex_input_def
    assert "n: float" in complex_input_def
    assert "b: Optional[bool]" in complex_input_def


@pytest.mark.asyncio
async def test_generate_mcp_sources(temp_dir, server_params):
    """Test the generate_mcp_sources function."""
    # Generate the MCP client sources
    result = await generate_mcp_sources(TEST_SERVER_NAME, server_params, temp_dir)

    # Check that the result is a list of sanitized tool names
    assert isinstance(result, list)
    assert "tool_1" in result
    assert TOOL2_NAME in result

    # Check that the server directory was created
    server_dir = temp_dir / TEST_SERVER_NAME
    assert server_dir.exists()

    # Check that __init__.py was created and contains the server_params
    init_file = server_dir / "__init__.py"
    assert init_file.exists()
    with open(init_file) as f:
        init_content = f.read()
        assert "SERVER_PARAMS = " in init_content

        # Check for transport-specific parameters
        if "command" in server_params:
            assert "command" in init_content
            assert "python" in init_content
        elif "url" in server_params:
            assert "url" in init_content
            assert server_params["type"] in init_content

    # Check that tool_1.py was created and contains the correct elements
    tool1_file = server_dir / "tool_1.py"
    assert tool1_file.exists()
    with open(tool1_file) as f:
        tool1_content = f.read()
        assert "class Params(" in tool1_content
        assert "s: str" in tool1_content
        assert "def tool_1(params: Params) -> str:" in tool1_content
        assert f'run_sync("{TOOL1_NAME}"' in tool1_content

    # Check that tool_2.py was created and contains the correct elements
    tool2_file = server_dir / f"{TOOL2_NAME}.py"
    assert tool2_file.exists()
    with open(tool2_file) as f:
        tool2_content = f.read()
        assert "class Params(" in tool2_content
        assert "s: str" in tool2_content
        assert f"def {TOOL2_NAME}(params: Params) -> str:" in tool2_content
        assert f'run_sync("{TOOL2_NAME}"' in tool2_content


@pytest.mark.asyncio
async def test_mcp_client(server_params):
    """Test the mcp_client context manager."""
    async with mcp_client(server_params) as streams:
        # Check that the streams are available
        assert streams is not None

        # Use ClientSession as shown in run_async
        async with ClientSession(*streams) as session:
            # Initialize the session
            await session.initialize()

            # Check that we can get the list of tools
            tools = await session.list_tools()
            assert tools is not None
            assert len(tools.tools) >= 2  # should have at least tool-1 and tool_2

            # Find our test tools
            tool_names = [tool.name for tool in tools.tools]
            assert TOOL1_NAME in tool_names, f"Tool {TOOL1_NAME} not found in tools"
            assert TOOL2_NAME in tool_names, f"Tool {TOOL2_NAME} not found in tools"

    # Test with invalid server_params
    with pytest.raises(ValueError, match='Neither a "command" nor a "url" key in server_params'):
        async with mcp_client({}) as _:
            pass


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tool_name,input_str,expected",
    [
        (TOOL1_NAME, "test_async_1", "You passed to tool 1: test_async_1"),
        (TOOL2_NAME, "test_async_2", "You passed to tool 2: test_async_2"),
    ],
)
async def test_run_async(server_params, tool_name, input_str, expected):
    """Test the run_async function."""
    result = await run_async(tool_name=tool_name, params={"s": input_str}, server_params=server_params)
    assert result == expected


@pytest.mark.asyncio
async def test_run_async_nonexistent_tool(server_params):
    """Test that run_async raises an exception for non-existent tools."""
    with pytest.raises(Exception):
        await run_async(tool_name=NONEXISTENT_TOOL, params={}, server_params=server_params)
