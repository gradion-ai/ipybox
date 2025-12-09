import asyncio

import pytest
import pytest_asyncio
import uvicorn
from fastapi import FastAPI

from ipybox.tool_exec.approval.client import ApprovalClient, ApprovalRequest
from ipybox.tool_exec.approval.server import ApprovalChannel

HOST = "localhost"
PORT = 8901


@pytest_asyncio.fixture
async def approval_channel():
    async with await _serve_channel() as channel:
        yield channel


async def _serve_channel(approval_required: bool = True, approval_timeout: float = 5.0):
    """Context manager that serves an ApprovalChannel over websocket."""
    channel = ApprovalChannel(approval_required, approval_timeout)
    app = FastAPI()
    app.websocket("/approval")(channel.connect)

    config = uvicorn.Config(app, HOST, PORT, log_level="warning")
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())

    while not server.started:
        await asyncio.sleep(0.01)

    class ChannelContext:
        async def __aenter__(self):
            return channel

        async def __aexit__(self, *_):
            await channel.disconnect()
            server.should_exit = True
            await task

    return ChannelContext()


class TestApprovalBasics:
    """Tests for basic approval request/response flow."""

    @pytest.mark.asyncio
    async def test_accept_request(self, approval_channel: ApprovalChannel):
        """Test that accepting a request returns True."""

        async def on_approval(request: ApprovalRequest):
            await request.accept()

        async with ApprovalClient(callback=on_approval, host=HOST, port=PORT):
            result = await approval_channel.request("test_server", "test_tool", {"arg1": "value1"})
            assert result is True

    @pytest.mark.asyncio
    async def test_reject_request(self, approval_channel: ApprovalChannel):
        """Test that rejecting a request returns False."""

        async def on_approval(request: ApprovalRequest):
            await request.reject()

        async with ApprovalClient(callback=on_approval, host=HOST, port=PORT):
            result = await approval_channel.request("test_server", "test_tool", {})
            assert result is False


class TestApprovalRequestData:
    """Tests for approval request data passing."""

    @pytest.mark.asyncio
    async def test_request_receives_server_name(self, approval_channel: ApprovalChannel):
        """Test that the callback receives the correct server name."""
        received_server_name = None

        async def on_approval(request: ApprovalRequest):
            nonlocal received_server_name
            received_server_name = request.server_name
            await request.accept()

        async with ApprovalClient(callback=on_approval, host=HOST, port=PORT):
            await approval_channel.request("my_server", "my_tool", {})

        assert received_server_name == "my_server"

    @pytest.mark.asyncio
    async def test_request_receives_tool_name(self, approval_channel: ApprovalChannel):
        """Test that the callback receives the correct tool name."""
        received_tool_name = None

        async def on_approval(request: ApprovalRequest):
            nonlocal received_tool_name
            received_tool_name = request.tool_name
            await request.accept()

        async with ApprovalClient(callback=on_approval, host=HOST, port=PORT):
            await approval_channel.request("my_server", "my_tool", {})

        assert received_tool_name == "my_tool"

    @pytest.mark.asyncio
    async def test_request_receives_tool_args(self, approval_channel: ApprovalChannel):
        """Test that the callback receives the correct tool args."""
        received_tool_args = None

        async def on_approval(request: ApprovalRequest):
            nonlocal received_tool_args
            received_tool_args = request.tool_args
            await request.accept()

        async with ApprovalClient(callback=on_approval, host=HOST, port=PORT):
            await approval_channel.request("my_server", "my_tool", {"key1": "value1", "key2": 42, "key3": [1, 2, 3]})

        assert received_tool_args == {"key1": "value1", "key2": 42, "key3": [1, 2, 3]}

    @pytest.mark.asyncio
    async def test_request_str_representation(self, approval_channel: ApprovalChannel):
        """Test ApprovalRequest string representation."""
        request_str = None

        async def on_approval(request: ApprovalRequest):
            nonlocal request_str
            request_str = str(request)
            await request.accept()

        async with ApprovalClient(callback=on_approval, host=HOST, port=PORT):
            await approval_channel.request("server", "tool", {"name": "test"})

        assert request_str == "server.tool(name='test')"


class TestApprovalNotRequired:
    """Tests for approval_required=False behavior."""

    @pytest.mark.asyncio
    async def test_auto_accept_when_not_required(self):
        """Test that requests are auto-accepted when approval_required=False."""
        channel = ApprovalChannel(approval_required=False)
        result = await channel.request("server", "tool", {})
        assert result is True


class TestApprovalTimeout:
    """Tests for approval timeout behavior."""

    @pytest.mark.asyncio
    async def test_timeout_when_no_response(self):
        """Test that request times out when client doesn't respond."""

        async def on_approval(request: ApprovalRequest):
            await asyncio.sleep(1)  # Longer than timeout

        async with await _serve_channel(approval_timeout=0.2) as channel:
            async with ApprovalClient(callback=on_approval, host=HOST, port=PORT):
                with pytest.raises(TimeoutError):
                    await channel.request("server", "tool", {})

    @pytest.mark.asyncio
    async def test_slow_response_within_timeout(self):
        """Test that a slow response within timeout succeeds."""

        async def on_approval(request: ApprovalRequest):
            await asyncio.sleep(0.2)
            await request.accept()

        async with await _serve_channel(approval_timeout=1.0) as channel:
            async with ApprovalClient(callback=on_approval, host=HOST, port=PORT):
                result = await channel.request("server", "tool", {})
                assert result is True


class TestApprovalConnection:
    """Tests for connection handling."""

    @pytest.mark.asyncio
    async def test_no_client_connected_raises_error(self, approval_channel: ApprovalChannel):
        """Test that requests fail when no client is connected."""
        with pytest.raises(RuntimeError, match="not connected"):
            await approval_channel.request("server", "tool", {})

    @pytest.mark.asyncio
    async def test_channel_open_property(self, approval_channel: ApprovalChannel):
        """Test the open property reflects connection state."""
        assert approval_channel.open is False

        async def on_approval(request: ApprovalRequest):
            await request.accept()

        async with ApprovalClient(callback=on_approval, host=HOST, port=PORT):
            assert approval_channel.open is True

        await asyncio.sleep(0.1)  # Wait for disconnect to propagate
        assert approval_channel.open is False

    @pytest.mark.asyncio
    async def test_client_disconnect_errors_pending_requests(self, approval_channel: ApprovalChannel):
        """Test that pending requests error when client disconnects."""
        request_received = asyncio.Event()

        async def on_approval(request: ApprovalRequest):
            # skip approval response
            request_received.set()

        client = ApprovalClient(callback=on_approval, host=HOST, port=PORT)
        await client.connect()

        request_task = asyncio.create_task(approval_channel.request("server", "tool", {}))

        await request_received.wait()
        await client.disconnect()

        with pytest.raises(RuntimeError, match="disconnected"):
            # waits for response but disconnect() errors future
            await request_task


class TestMultipleRequests:
    """Tests for handling multiple concurrent requests."""

    @pytest.mark.asyncio
    async def test_sequential_requests(self, approval_channel: ApprovalChannel):
        """Test multiple sequential requests."""
        request_count = 0

        async def on_approval(request: ApprovalRequest):
            nonlocal request_count
            request_count += 1
            await request.accept()

        async with ApprovalClient(callback=on_approval, host=HOST, port=PORT):
            for i in range(5):
                result = await approval_channel.request("server", f"tool_{i}", {"index": i})
                assert result is True

        assert request_count == 5

    @pytest.mark.asyncio
    async def test_concurrent_requests(self, approval_channel: ApprovalChannel):
        """Test multiple concurrent requests."""
        requests_received = []

        async def on_approval(request: ApprovalRequest):
            requests_received.append(request.tool_name)
            await asyncio.sleep(0.1)
            await request.accept()

        async with ApprovalClient(callback=on_approval, host=HOST, port=PORT):
            tasks = [approval_channel.request("server", f"tool_{i}", {}) for i in range(3)]
            results = await asyncio.gather(*tasks)

        assert all(r is True for r in results)
        assert len(requests_received) == 3
        assert set(requests_received) == {"tool_0", "tool_1", "tool_2"}

    @pytest.mark.asyncio
    async def test_mixed_accept_reject_concurrent(self, approval_channel: ApprovalChannel):
        """Test concurrent requests with mixed accept/reject responses."""

        async def on_approval(request: ApprovalRequest):
            if request.tool_args.get("index", 0) % 2 == 0:
                await request.accept()
            else:
                await request.reject()

        async with ApprovalClient(callback=on_approval, host=HOST, port=PORT):
            tasks = [approval_channel.request("server", "tool", {"index": i}) for i in range(4)]
            results = await asyncio.gather(*tasks)

        assert results == [True, False, True, False]
