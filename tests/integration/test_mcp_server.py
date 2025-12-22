import sys
from pathlib import Path

import pytest
import pytest_asyncio

from ipybox.mcp_client import MCPClient
from tests.integration.mcp_server import STDIO_SERVER_PATH

MCP_SERVER_NAME = "test_mcp"


@pytest_asyncio.fixture
async def mcp_client(tmp_path: Path):
    """Create an MCPClient connected to the ipybox MCP server."""
    # Create .env file with KERNEL_ENV_ prefixed variable for testing
    dotenv_file = tmp_path / ".env"
    dotenv_file.write_text("KERNEL_ENV_TEST_VAR=test_value_from_dotenv\n")

    server_params = {
        "command": sys.executable,
        "args": ["-m", "ipybox.mcp_server", "--workspace", str(tmp_path), "--log-level", "ERROR"],
    }
    async with MCPClient(server_params, connect_timeout=30) as client:
        yield client


class TestBasicExecution:
    """Basic MCP server functionality."""

    @pytest.mark.asyncio
    async def test_simple_code_execution(self, mcp_client: MCPClient):
        """Test executing a simple print statement."""
        result = await mcp_client.run("execute_ipython_cell", {"code": "print('hello world')"})

        assert result == "hello world"

    @pytest.mark.asyncio
    async def test_expression_result(self, mcp_client: MCPClient):
        """Test that expression results are returned."""
        result = await mcp_client.run("execute_ipython_cell", {"code": "2 + 2"})

        assert result == "4"

    @pytest.mark.asyncio
    async def test_code_execution_error(self, mcp_client: MCPClient):
        """Test that execution errors are raised."""
        with pytest.raises(Exception) as exc_info:
            await mcp_client.run("execute_ipython_cell", {"code": "raise ValueError('test error')"})

        assert "ValueError" in str(exc_info.value)
        assert "test error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_state_persistence(self, mcp_client: MCPClient):
        """Test that kernel state persists across executions."""
        await mcp_client.run("execute_ipython_cell", {"code": "x = 42"})
        result = await mcp_client.run("execute_ipython_cell", {"code": "print(x)"})

        assert result == "42"

    @pytest.mark.asyncio
    async def test_max_output_chars_truncation(self, mcp_client: MCPClient):
        """Test that output is truncated when exceeding max_output_chars."""
        # Generate output longer than the limit
        code = "print('x' * 100)"
        result = await mcp_client.run("execute_ipython_cell", {"code": code, "max_output_chars": 50})

        assert isinstance(result, str)
        assert len(result) > 50  # Includes truncation message
        assert result.startswith("x" * 50)
        assert "[Output truncated: exceeded 50 character limit]" in result

    @pytest.mark.asyncio
    async def test_max_output_chars_no_truncation(self, mcp_client: MCPClient):
        """Test that output is not truncated when within max_output_chars."""
        code = "print('hello world')"
        result = await mcp_client.run("execute_ipython_cell", {"code": code, "max_output_chars": 100})

        assert isinstance(result, str)
        assert result == "hello world"
        assert "[Output truncated" not in result

    @pytest.mark.asyncio
    async def test_max_output_chars_default(self, mcp_client: MCPClient):
        """Test that default max_output_chars (5000) is used when not specified."""
        # Generate output slightly over 5000 chars
        code = "print('x' * 5001)"
        result = await mcp_client.run("execute_ipython_cell", {"code": code})

        assert isinstance(result, str)
        assert "[Output truncated: exceeded 5000 character limit]" in result
        assert result.startswith("x" * 5000)

    @pytest.mark.asyncio
    async def test_dotenv_kernel_env_var_available(self, mcp_client: MCPClient):
        """Test that KERNEL_ENV_ variables from .env are available in kernel."""
        code = "import os; print(os.environ.get('TEST_VAR', 'NOT_FOUND'))"
        result = await mcp_client.run("execute_ipython_cell", {"code": code})

        assert result == "test_value_from_dotenv"


class TestMcpServerRegistration:
    """MCP server registration tests."""

    @pytest.mark.asyncio
    async def test_register_mcp_server_returns_tool_names(self, mcp_client: MCPClient):
        """Test that register_mcp_server returns tool names."""
        server_params = {
            "command": "python",
            "args": [str(STDIO_SERVER_PATH)],
        }

        result = await mcp_client.run(
            "register_mcp_server",
            {"server_name": MCP_SERVER_NAME, "server_params": server_params},
        )
        assert isinstance(result, str)

        tool_names = result.split("\n")
        assert "tool_1" in tool_names
        assert "tool_2" in tool_names
        assert "tool_3" in tool_names

    @pytest.mark.asyncio
    async def test_registered_tools_generate_sources(self, mcp_client: MCPClient, tmp_path: Path):
        """Test that registration generates importable sources in the workspace."""
        server_params = {
            "command": "python",
            "args": [str(STDIO_SERVER_PATH)],
        }

        await mcp_client.run(
            "register_mcp_server",
            {"server_name": MCP_SERVER_NAME, "server_params": server_params},
        )

        # Verify the package was generated
        package_dir = tmp_path / "mcptools" / MCP_SERVER_NAME
        assert package_dir.exists()
        assert (package_dir / "__init__.py").exists()
        assert (package_dir / "tool_1.py").exists()
        assert (package_dir / "tool_2.py").exists()
        assert (package_dir / "tool_3.py").exists()

    @pytest.mark.asyncio
    async def test_registered_tools_are_callable(self, mcp_client: MCPClient):
        """Test that registered tools can be imported and called via execute_ipython_cell."""
        server_params = {
            "command": "python",
            "args": [str(STDIO_SERVER_PATH)],
        }

        await mcp_client.run(
            "register_mcp_server",
            {"server_name": MCP_SERVER_NAME, "server_params": server_params},
        )

        # Sources are generated at mcptools/{server_name}/
        code = f"""
from mcptools.{MCP_SERVER_NAME}.tool_2 import run, Params
result = run(Params(s="hello"))
print(result)
"""
        result = await mcp_client.run("execute_ipython_cell", {"code": code})
        assert isinstance(result, str)

        assert "You passed to tool 2: hello" in result


class TestReset:
    """Kernel reset tests."""

    @pytest.mark.asyncio
    async def test_reset_clears_kernel_state(self, mcp_client: MCPClient):
        """Test that reset clears kernel state."""
        # Set a variable
        await mcp_client.run("execute_ipython_cell", {"code": "x = 42"})

        # Verify it exists
        result = await mcp_client.run("execute_ipython_cell", {"code": "print(x)"})
        assert result == "42"

        # Reset
        await mcp_client.run("reset", {})

        # Verify the variable no longer exists
        with pytest.raises(Exception) as exc_info:
            await mcp_client.run("execute_ipython_cell", {"code": "print(x)"})
        assert "NameError" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_reset_allows_continued_execution(self, mcp_client: MCPClient):
        """Test that reset allows continued execution."""
        # Set state and reset
        await mcp_client.run("execute_ipython_cell", {"code": "x = 42"})
        await mcp_client.run("reset", {})

        # Verify we can still execute code
        result = await mcp_client.run("execute_ipython_cell", {"code": "print('after reset')"})

        assert result == "after reset"


@pytest.mark.skipif(sys.platform != "darwin", reason="Sandbox tests only run on macOS")
class TestSandbox:
    """Tests for sandbox configuration."""

    HTTP_CODE = """
import urllib.request
req = urllib.request.Request(
    url="https://example.org",
    headers={"User-Agent": "Mozilla/5.0"},
)
response = urllib.request.urlopen(req)
content = response.read().decode('utf-8')
print(content)
"""

    @pytest_asyncio.fixture
    async def mcp_client_custom_sandbox(self, tmp_path: Path):
        """Create an MCPClient with custom sandbox config (example.org allowed)."""
        sandbox_config = Path("tests", "integration", "sandbox.json").absolute()
        server_params = {
            "command": sys.executable,
            "args": [
                "-m",
                "ipybox.mcp_server",
                "--workspace",
                str(tmp_path),
                "--log-level",
                "ERROR",
                "--sandbox",
                "--sandbox-config",
                str(sandbox_config),
            ],
        }
        async with MCPClient(server_params, connect_timeout=30) as client:
            yield client

    @pytest.mark.asyncio
    async def test_custom_sandbox_allows_example_org(self, mcp_client_custom_sandbox: MCPClient):
        """Test that custom sandbox config allows example.org access."""
        result = await mcp_client_custom_sandbox.run("execute_ipython_cell", {"code": self.HTTP_CODE})

        assert result is not None
        assert "Example Domain" in result
