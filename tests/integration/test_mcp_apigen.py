import importlib
import os
import sys
import tempfile
from pathlib import Path

import pytest
import pytest_asyncio

from ipybox.mcp_apigen import generate_mcp_sources
from ipybox.tool_exec.server import ToolServer
from ipybox.utils import arun
from tests.integration.mcp_server import STDIO_SERVER_PATH

TOOL_SERVER_PORT = 8920
MCP_SERVER_NAME = "test_mcp"


@pytest_asyncio.fixture(scope="module")
async def generated_package():
    """Generate a Python tool API to a temp directory."""
    server_params = {
        "command": "python",
        "args": [str(STDIO_SERVER_PATH)],
    }

    with tempfile.TemporaryDirectory() as tmp_dir:
        root_dir = Path(tmp_dir)

        # Generate sources
        tool_names = await generate_mcp_sources(
            server_name=MCP_SERVER_NAME,
            server_params=server_params,
            root_dir=root_dir,
        )

        # Add temp dir to sys.path for imports
        sys.path.insert(0, str(root_dir))

        yield {
            "root_dir": root_dir,
            "package_dir": root_dir / MCP_SERVER_NAME,
            "tool_names": tool_names,
            "server_params": server_params,
        }

        # Cleanup sys.path and modules
        sys.path.remove(str(root_dir))
        modules_to_remove = [k for k in sys.modules if k.startswith(MCP_SERVER_NAME)]
        for mod in modules_to_remove:
            del sys.modules[mod]


@pytest_asyncio.fixture
async def tool_server():
    """Start a ToolServer for executing the generated API."""
    async with ToolServer(port=TOOL_SERVER_PORT, log_level="WARNING") as server:
        yield server


class TestGenerateMcpSources:
    """Tests for generate_mcp_sources function."""

    def test_generates_expected_files(self, generated_package: dict):
        """Test that expected module files are generated."""
        package_dir = generated_package["package_dir"]

        assert (package_dir / "__init__.py").exists()
        assert (package_dir / "tool_1.py").exists()  # tool-1 sanitized
        assert (package_dir / "tool_2.py").exists()
        assert (package_dir / "tool_3.py").exists()

    def test_returns_sanitized_tool_names(self, generated_package: dict):
        """Test that generate_mcp_sources returns sanitized tool names."""
        tool_names = generated_package["tool_names"]

        assert "tool_1" in tool_names  # tool-1 sanitized to tool_1
        assert "tool_2" in tool_names
        assert "tool_3" in tool_names

    @pytest.mark.asyncio
    async def test_tool_with_unstructured_output(self, generated_package: dict, tool_server: ToolServer):
        """Test executing a generated tool with unstructured (string) output."""
        # Set environment variables for the generated CLIENT
        os.environ["TOOL_SERVER_PORT"] = str(TOOL_SERVER_PORT)

        # Import generated module
        tool_2 = importlib.import_module(f"{MCP_SERVER_NAME}.tool_2")

        def call_tool():
            return tool_2.run(tool_2.Params(s="hello"))

        result = await arun(call_tool)
        assert result == "You passed to tool 2: hello"

    @pytest.mark.asyncio
    async def test_hyphenated_tool_name_works(self, generated_package: dict, tool_server: ToolServer):
        """Test that tool-1 (hyphenated) is accessible via sanitized name tool_1."""
        os.environ["TOOL_SERVER_PORT"] = str(TOOL_SERVER_PORT)

        # tool-1 was renamed in MCP server, but we access it via sanitized module name tool_1
        tool_1 = importlib.import_module(f"{MCP_SERVER_NAME}.tool_1")

        def call_tool():
            return tool_1.run(tool_1.Params(s="hyphen_test"))

        result = await arun(call_tool)
        assert result == "You passed to tool 1: hyphen_test"

    @pytest.mark.asyncio
    async def test_tool_with_structured_output(self, generated_package: dict, tool_server: ToolServer):
        """Test executing a generated tool with structured output."""
        os.environ["TOOL_SERVER_PORT"] = str(TOOL_SERVER_PORT)

        # Import generated module with structured output
        tool_3 = importlib.import_module(f"{MCP_SERVER_NAME}.tool_3")

        def call_tool():
            return tool_3.run(tool_3.Params(name="test", level=2))

        result = await arun(call_tool)

        # Result should be a Pydantic model instance
        assert hasattr(result, "status")
        assert hasattr(result, "inner")
        assert hasattr(result, "count")

        assert result.status == "completed_test"
        assert result.count == 4  # len("test")
        assert result.inner.code == 200  # level * 100
        assert result.inner.details == "Processing test at level 2"

    @pytest.mark.asyncio
    async def test_multiple_tool_calls(self, generated_package: dict, tool_server: ToolServer):
        """Test multiple sequential calls to the generated API."""
        os.environ["TOOL_SERVER_PORT"] = str(TOOL_SERVER_PORT)

        tool_1 = importlib.import_module(f"{MCP_SERVER_NAME}.tool_1")
        tool_2 = importlib.import_module(f"{MCP_SERVER_NAME}.tool_2")

        def call_tools():
            r1 = tool_1.run(tool_1.Params(s="first"))
            r2 = tool_2.run(tool_2.Params(s="second"))
            r3 = tool_1.run(tool_1.Params(s="third"))
            return r1, r2, r3

        result = await arun(call_tools)
        assert result[0] == "You passed to tool 1: first"
        assert result[1] == "You passed to tool 2: second"
        assert result[2] == "You passed to tool 1: third"
