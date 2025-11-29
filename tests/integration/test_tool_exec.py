import asyncio
from typing import Any, Awaitable, Callable

import pytest
import pytest_asyncio

from ipybox.tool_exec.approval.client import ApprovalClient, ApprovalRequest
from ipybox.tool_exec.client import ToolRunner, ToolRunnerError
from ipybox.tool_exec.server import ToolServer
from ipybox.utils import arun

RunToolFunc = Callable[[ToolRunner, str, dict[str, Any]], Awaitable[dict[str, Any] | str | None]]

TOOL_SERVER_PORT = 8910
MCP_SERVER_NAME = "test_mcp_server"


@pytest_asyncio.fixture
async def tool_server():
    """Start a ToolServer with approval disabled."""
    async with ToolServer(port=TOOL_SERVER_PORT, approval_required=False, log_level="WARNING") as server:
        yield server


@pytest_asyncio.fixture
async def tool_server_with_approval():
    """Start a ToolServer with approval enabled."""
    async with ToolServer(port=TOOL_SERVER_PORT, approval_required=True, log_level="WARNING") as server:
        yield server


@pytest.fixture(params=["async", "sync"])
def run_tool(request) -> RunToolFunc:
    """Fixture that provides tool execution in both async and sync modes."""
    if request.param == "async":

        async def _run(runner: ToolRunner, tool_name: str, tool_args: dict[str, Any]) -> dict[str, Any] | str | None:
            return await runner.run(tool_name, tool_args)
    else:

        async def _run(runner: ToolRunner, tool_name: str, tool_args: dict[str, Any]) -> dict[str, Any] | str | None:
            return await arun(runner.run_sync, tool_name, tool_args)

    return _run


class TestToolServerLifecycle:
    """Tests for ToolServer start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_start_twice_raises_error(self):
        """Test that starting a running server raises RuntimeError."""
        async with ToolServer(port=TOOL_SERVER_PORT, log_level="WARNING") as server:
            with pytest.raises(RuntimeError, match="already running"):
                await server.start()

    @pytest.mark.asyncio
    async def test_stop_idempotent(self):
        """Test that stopping a stopped server is safe."""
        server = ToolServer(port=TOOL_SERVER_PORT, log_level="WARNING")
        await server.start()
        await server.stop()
        await server.stop()  # Should not raise

    @pytest.mark.asyncio
    async def test_status_endpoint(self):
        """Test the status endpoint returns ok."""
        import aiohttp

        async with ToolServer(port=TOOL_SERVER_PORT, log_level="WARNING"):
            async with aiohttp.ClientSession() as session:
                async with session.get(f"http://localhost:{TOOL_SERVER_PORT}/status") as response:
                    assert response.status == 200
                    data = await response.json()
                    assert data == {"status": "ok"}


class TestToolRunnerBasicOperations:
    """Tests for basic ToolRunner operations with stdio transport."""

    @pytest.mark.asyncio
    async def test_run_tool_1(
        self, stdio_server_params: dict[str, Any], tool_server: ToolServer, run_tool: RunToolFunc
    ):
        """Test running tool-1 (renamed from tool_1) with string input."""
        runner = ToolRunner(MCP_SERVER_NAME, stdio_server_params, port=TOOL_SERVER_PORT)
        result = await run_tool(runner, "tool-1", {"s": "hello"})
        assert result == "You passed to tool 1: hello"

    @pytest.mark.asyncio
    async def test_run_tool_2(
        self, stdio_server_params: dict[str, Any], tool_server: ToolServer, run_tool: RunToolFunc
    ):
        """Test running tool_2 with string input."""
        runner = ToolRunner(MCP_SERVER_NAME, stdio_server_params, port=TOOL_SERVER_PORT)
        result = await run_tool(runner, "tool_2", {"s": "world"})
        assert result == "You passed to tool 2: world"

    @pytest.mark.asyncio
    async def test_multiple_tool_calls(
        self, stdio_server_params: dict[str, Any], tool_server: ToolServer, run_tool: RunToolFunc
    ):
        """Test multiple sequential tool calls."""
        runner = ToolRunner(MCP_SERVER_NAME, stdio_server_params, port=TOOL_SERVER_PORT)

        result1 = await run_tool(runner, "tool-1", {"s": "first"})
        result2 = await run_tool(runner, "tool_2", {"s": "second"})
        result3 = await run_tool(runner, "tool-1", {"s": "third"})

        assert result1 == "You passed to tool 1: first"
        assert result2 == "You passed to tool 2: second"
        assert result3 == "You passed to tool 1: third"

    @pytest.mark.asyncio
    async def test_concurrent_tool_calls(
        self, stdio_server_params: dict[str, Any], tool_server: ToolServer, run_tool: RunToolFunc
    ):
        """Test concurrent tool calls."""
        runner = ToolRunner(MCP_SERVER_NAME, stdio_server_params, port=TOOL_SERVER_PORT)

        results = await asyncio.gather(
            run_tool(runner, "tool-1", {"s": "a"}),
            run_tool(runner, "tool_2", {"s": "b"}),
            run_tool(runner, "tool-1", {"s": "c"}),
        )

        assert "You passed to tool 1: a" in results
        assert "You passed to tool 2: b" in results
        assert "You passed to tool 1: c" in results


class TestToolRunnerStructuredOutput:
    """Tests for tool_3's nested structured output."""

    @pytest.mark.asyncio
    async def test_structured_output_basic(
        self, stdio_server_params: dict[str, Any], tool_server: ToolServer, run_tool: RunToolFunc
    ):
        """Test tool_3 returns nested structured output."""
        runner = ToolRunner(MCP_SERVER_NAME, stdio_server_params, port=TOOL_SERVER_PORT)
        result = await run_tool(runner, "tool_3", {"name": "test", "level": 2})

        assert isinstance(result, dict)
        assert result["status"] == "completed_test"
        assert result["count"] == 4  # len("test")

        inner = result["inner"]
        assert isinstance(inner, dict)
        assert inner["code"] == 200  # level * 100
        assert inner["details"] == "Processing test at level 2"


class TestToolRunnerSpecialToolNames:
    """Tests for tools with special naming (tool-1 vs tool_1)."""

    @pytest.mark.asyncio
    async def test_tool_with_hyphenated_name(
        self, stdio_server_params: dict[str, Any], tool_server: ToolServer, run_tool: RunToolFunc
    ):
        """Test that tool-1 (hyphenated) is accessible by its registered name."""
        runner = ToolRunner(MCP_SERVER_NAME, stdio_server_params, port=TOOL_SERVER_PORT)
        result = await run_tool(runner, "tool-1", {"s": "hyphen_test"})
        assert result == "You passed to tool 1: hyphen_test"

    @pytest.mark.asyncio
    async def test_tool_1_original_name_fails(
        self, stdio_server_params: dict[str, Any], tool_server: ToolServer, run_tool: RunToolFunc
    ):
        """Test that tool_1 (underscore) is NOT accessible - it was renamed to tool-1."""
        runner = ToolRunner(MCP_SERVER_NAME, stdio_server_params, port=TOOL_SERVER_PORT)
        with pytest.raises(ToolRunnerError):
            await run_tool(runner, "tool_1", {"s": "should_fail"})


class TestToolRunnerTransports:
    """Tests for different MCP transport types (stdio, http, sse)."""

    @pytest.mark.asyncio
    async def test_stdio_transport(
        self, stdio_server_params: dict[str, Any], tool_server: ToolServer, run_tool: RunToolFunc
    ):
        """Test tool execution with stdio transport."""
        runner = ToolRunner(MCP_SERVER_NAME, stdio_server_params, port=TOOL_SERVER_PORT)
        result = await run_tool(runner, "tool_2", {"s": "stdio_test"})
        assert result == "You passed to tool 2: stdio_test"

    @pytest.mark.asyncio
    async def test_http_transport(
        self, http_server_params: dict[str, Any], tool_server: ToolServer, run_tool: RunToolFunc
    ):
        """Test tool execution with streamable HTTP transport."""
        runner = ToolRunner("http_server", http_server_params, port=TOOL_SERVER_PORT)
        result = await run_tool(runner, "tool_2", {"s": "http_test"})
        assert result == "You passed to tool 2: http_test"

    @pytest.mark.asyncio
    async def test_http_transport_structured_output(
        self, http_server_params: dict[str, Any], tool_server: ToolServer, run_tool: RunToolFunc
    ):
        """Test structured output with HTTP transport."""
        runner = ToolRunner("http_server", http_server_params, port=TOOL_SERVER_PORT)
        result = await run_tool(runner, "tool_3", {"name": "http", "level": 3})

        assert isinstance(result, dict)
        assert result["status"] == "completed_http"
        assert result["inner"]["code"] == 300

    @pytest.mark.asyncio
    async def test_sse_transport(
        self, sse_server_params: dict[str, Any], tool_server: ToolServer, run_tool: RunToolFunc
    ):
        """Test tool execution with SSE transport."""
        runner = ToolRunner("sse_server", sse_server_params, port=TOOL_SERVER_PORT)
        result = await run_tool(runner, "tool_2", {"s": "sse_test"})
        assert result == "You passed to tool 2: sse_test"

    @pytest.mark.asyncio
    async def test_sse_transport_structured_output(
        self, sse_server_params: dict[str, Any], tool_server: ToolServer, run_tool: RunToolFunc
    ):
        """Test structured output with SSE transport."""
        runner = ToolRunner("sse_server", sse_server_params, port=TOOL_SERVER_PORT)
        result = await run_tool(runner, "tool_3", {"name": "sse", "level": 1})

        assert isinstance(result, dict)
        assert result["status"] == "completed_sse"
        assert result["inner"]["code"] == 100

    @pytest.mark.asyncio
    async def test_mixed_transports(
        self,
        stdio_server_params: dict[str, Any],
        http_server_params: dict[str, Any],
        sse_server_params: dict[str, Any],
        tool_server: ToolServer,
        run_tool: RunToolFunc,
    ):
        """Test using multiple transports with the same ToolServer."""
        stdio_runner = ToolRunner("stdio_server", stdio_server_params, port=TOOL_SERVER_PORT)
        http_runner = ToolRunner("http_server", http_server_params, port=TOOL_SERVER_PORT)
        sse_runner = ToolRunner("sse_server", sse_server_params, port=TOOL_SERVER_PORT)

        stdio_result = await run_tool(stdio_runner, "tool-1", {"s": "stdio"})
        http_result = await run_tool(http_runner, "tool-1", {"s": "http"})
        sse_result = await run_tool(sse_runner, "tool-1", {"s": "sse"})

        assert stdio_result == "You passed to tool 1: stdio"
        assert http_result == "You passed to tool 1: http"
        assert sse_result == "You passed to tool 1: sse"


class TestToolRunnerErrors:
    """Tests for error handling in ToolRunner."""

    @pytest.mark.asyncio
    async def test_unknown_tool_raises_error(
        self, stdio_server_params: dict[str, Any], tool_server: ToolServer, run_tool: RunToolFunc
    ):
        """Test that calling an unknown tool raises ToolRunnerError."""
        runner = ToolRunner(MCP_SERVER_NAME, stdio_server_params, port=TOOL_SERVER_PORT)
        with pytest.raises(ToolRunnerError):
            await run_tool(runner, "nonexistent_tool", {})

    @pytest.mark.asyncio
    async def test_invalid_args_raises_error(
        self, stdio_server_params: dict[str, Any], tool_server: ToolServer, run_tool: RunToolFunc
    ):
        """Test that invalid tool arguments raise ToolRunnerError."""
        runner = ToolRunner(MCP_SERVER_NAME, stdio_server_params, port=TOOL_SERVER_PORT)
        with pytest.raises(ToolRunnerError):
            await run_tool(runner, "tool_3", {"wrong_arg": "value"})

    @pytest.mark.asyncio
    async def test_missing_required_args_raises_error(
        self, stdio_server_params: dict[str, Any], tool_server: ToolServer, run_tool: RunToolFunc
    ):
        """Test that missing required arguments raise ToolRunnerError."""
        runner = ToolRunner(MCP_SERVER_NAME, stdio_server_params, port=TOOL_SERVER_PORT)
        with pytest.raises(ToolRunnerError):
            await run_tool(runner, "tool_3", {"name": "test"})  # Missing 'level'


class TestToolRunnerReset:
    """Tests for ToolServer reset functionality."""

    @pytest.mark.asyncio
    async def test_reset(
        self,
        stdio_server_params: dict[str, Any],
        http_server_params: dict[str, Any],
        tool_server: ToolServer,
        run_tool: RunToolFunc,
    ):
        """Test that reset clears all managed MCP servers."""
        stdio_runner = ToolRunner("stdio_server", stdio_server_params, port=TOOL_SERVER_PORT)
        http_runner = ToolRunner("http_server", http_server_params, port=TOOL_SERVER_PORT)

        # No MCP clients initially
        assert len(tool_server._mcp_clients) == 0

        # Start both servers
        await run_tool(stdio_runner, "tool-1", {"s": "stdio"})
        await run_tool(http_runner, "tool-1", {"s": "http"})

        # Two MCP clients should be registered
        assert len(tool_server._mcp_clients) == 2

        # Reset all
        await stdio_runner.reset()

        # MCP clients should be cleared
        assert len(tool_server._mcp_clients) == 0

        # Both should still work after reset (MCP servers will be restarted)
        result1 = await run_tool(stdio_runner, "tool-1", {"s": "stdio_after"})
        result2 = await run_tool(http_runner, "tool-1", {"s": "http_after"})

        assert result1 == "You passed to tool 1: stdio_after"
        assert result2 == "You passed to tool 1: http_after"

        # Two MCP clients should be registered again
        assert len(tool_server._mcp_clients) == 2


class TestToolServerWithApproval:
    """Basic integration tests for ToolServer with approval_required=True.

    Detailed approval testing is in test_tool_approval.py.
    These tests verify that ToolServer integrates correctly with the approval system.
    """

    @pytest.mark.asyncio
    async def test_tool_call_approved(
        self,
        stdio_server_params: dict[str, Any],
        tool_server_with_approval: ToolServer,
        run_tool: RunToolFunc,
    ):
        """Test that approved tool calls succeed."""
        runner = ToolRunner(MCP_SERVER_NAME, stdio_server_params, port=TOOL_SERVER_PORT)

        async def approve_all(request: ApprovalRequest):
            await request.approve()

        async with ApprovalClient(callback=approve_all, port=TOOL_SERVER_PORT):
            result = await run_tool(runner, "tool-1", {"s": "approved"})
            assert result == "You passed to tool 1: approved"

    @pytest.mark.asyncio
    async def test_tool_call_rejected(
        self,
        stdio_server_params: dict[str, Any],
        tool_server_with_approval: ToolServer,
        run_tool: RunToolFunc,
    ):
        """Test that rejected tool calls raise ToolRunnerError."""
        runner = ToolRunner(MCP_SERVER_NAME, stdio_server_params, port=TOOL_SERVER_PORT)

        async def reject_all(request: ApprovalRequest):
            await request.reject()

        async with ApprovalClient(callback=reject_all, port=TOOL_SERVER_PORT):
            with pytest.raises(ToolRunnerError, match="denied"):
                await run_tool(runner, "tool-1", {"s": "rejected"})

    @pytest.mark.asyncio
    async def test_approval_receives_correct_data(
        self,
        stdio_server_params: dict[str, Any],
        tool_server_with_approval: ToolServer,
        run_tool: RunToolFunc,
    ):
        """Test that approval callback receives correct tool call data."""
        runner = ToolRunner(MCP_SERVER_NAME, stdio_server_params, port=TOOL_SERVER_PORT)
        received_request: ApprovalRequest | None = None

        async def capture_request(request: ApprovalRequest):
            nonlocal received_request
            received_request = request
            await request.approve()

        async with ApprovalClient(callback=capture_request, port=TOOL_SERVER_PORT):
            await run_tool(runner, "tool_3", {"name": "test_name", "level": 42})

        assert received_request is not None
        assert received_request.server_name == MCP_SERVER_NAME
        assert received_request.tool_name == "tool_3"
        assert received_request.tool_args == {"name": "test_name", "level": 42}

    @pytest.mark.asyncio
    async def test_selective_approval(
        self,
        stdio_server_params: dict[str, Any],
        tool_server_with_approval: ToolServer,
        run_tool: RunToolFunc,
    ):
        """Test selective approval based on tool name."""
        runner = ToolRunner(MCP_SERVER_NAME, stdio_server_params, port=TOOL_SERVER_PORT)

        async def selective_approve(request: ApprovalRequest):
            if request.tool_name == "tool_2":
                await request.reject()
            else:
                await request.approve()

        async with ApprovalClient(callback=selective_approve, port=TOOL_SERVER_PORT):
            # tool-1 should succeed
            result = await run_tool(runner, "tool-1", {"s": "allowed"})
            assert result == "You passed to tool 1: allowed"

            # tool_2 should be rejected
            with pytest.raises(ToolRunnerError, match="denied"):
                await run_tool(runner, "tool_2", {"s": "blocked"})

    @pytest.mark.asyncio
    async def test_no_approval_client_raises_error(
        self,
        stdio_server_params: dict[str, Any],
        tool_server_with_approval: ToolServer,
        run_tool: RunToolFunc,
    ):
        """Test that tool calls fail when no ApprovalClient is connected."""
        runner = ToolRunner(MCP_SERVER_NAME, stdio_server_params, port=TOOL_SERVER_PORT)

        with pytest.raises(ToolRunnerError, match="failed"):
            await run_tool(runner, "tool-1", {"s": "no_client"})

    @pytest.mark.asyncio
    async def test_approval_timeout(self, stdio_server_params: dict[str, Any], run_tool: RunToolFunc):
        """Test that tool calls fail when approval times out."""
        async with ToolServer(port=TOOL_SERVER_PORT, approval_required=True, approval_timeout=0.1, log_level="WARNING"):
            runner = ToolRunner(MCP_SERVER_NAME, stdio_server_params, port=TOOL_SERVER_PORT)

            async def never_respond(request: ApprovalRequest):
                pass  # Never calls approve() or reject()

            async with ApprovalClient(callback=never_respond, port=TOOL_SERVER_PORT):
                with pytest.raises(ToolRunnerError, match="expired"):
                    await run_tool(runner, "tool-1", {"s": "timeout_test"})
