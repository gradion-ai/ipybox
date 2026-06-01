"""Unit tests for the configurable kernel initialization timeout."""

import pytest

from ipybox.code_exec import CodeExecutor
from ipybox.kernel_mgr.client import KernelClient


class TestKernelClientInitTimeout:
    """Tests for `KernelClient.kernel_init_timeout` wiring."""

    def test_default_value(self):
        client = KernelClient()
        assert client.kernel_init_timeout == 10

    def test_constructor_value_is_stored(self):
        client = KernelClient(kernel_init_timeout=45)
        assert client.kernel_init_timeout == 45

    @pytest.mark.asyncio
    async def test_init_kernel_uses_configured_timeout(self, monkeypatch: pytest.MonkeyPatch):
        client = KernelClient(kernel_init_timeout=42)

        captured: dict[str, float | None] = {}

        async def fake_execute(code: str, timeout: float | None = None):
            captured["timeout"] = timeout

        monkeypatch.setattr(client, "execute", fake_execute)

        await client._init_kernel()
        assert captured["timeout"] == 42

    @pytest.mark.asyncio
    async def test_init_kernel_explicit_timeout_overrides_constructor(self, monkeypatch: pytest.MonkeyPatch):
        client = KernelClient(kernel_init_timeout=42)

        captured: dict[str, float | None] = {}

        async def fake_execute(code: str, timeout: float | None = None):
            captured["timeout"] = timeout

        monkeypatch.setattr(client, "execute", fake_execute)

        await client._init_kernel(7)
        assert captured["timeout"] == 7

    @pytest.mark.asyncio
    async def test_connect_threads_timeout_to_init_kernel(self, monkeypatch: pytest.MonkeyPatch):
        client = KernelClient(kernel_init_timeout=42)

        async def fake_create_kernel():
            return "kernel-id"

        async def fake_websocket_connect(*args: object, **kwargs: object):
            return object()

        captured: dict[str, float | None] = {}

        async def fake_init_kernel(timeout: float | None = None):
            captured["timeout"] = timeout

        monkeypatch.setattr(client, "_create_kernel", fake_create_kernel)
        monkeypatch.setattr("ipybox.kernel_mgr.client.websocket_connect", fake_websocket_connect)
        monkeypatch.setattr(client, "_init_kernel", fake_init_kernel)

        await client.connect(kernel_init_timeout=9)
        assert captured["timeout"] == 9

    @pytest.mark.asyncio
    async def test_connect_without_override_passes_none(self, monkeypatch: pytest.MonkeyPatch):
        client = KernelClient(kernel_init_timeout=42)

        async def fake_create_kernel():
            return "kernel-id"

        async def fake_websocket_connect(*args: object, **kwargs: object):
            return object()

        captured: dict[str, float | None] = {}

        async def fake_init_kernel(timeout: float | None = None):
            captured["timeout"] = timeout

        monkeypatch.setattr(client, "_create_kernel", fake_create_kernel)
        monkeypatch.setattr("ipybox.kernel_mgr.client.websocket_connect", fake_websocket_connect)
        monkeypatch.setattr(client, "_init_kernel", fake_init_kernel)

        await client.connect()
        # None falls back to the constructor value inside _init_kernel.
        assert captured["timeout"] is None


class TestCodeExecutorInitTimeout:
    """Tests for `CodeExecutor.kernel_init_timeout` wiring."""

    def test_default_value(self):
        executor = CodeExecutor()
        assert executor.kernel_init_timeout == 10

    def test_constructor_value_is_stored(self):
        executor = CodeExecutor(kernel_init_timeout=45)
        assert executor.kernel_init_timeout == 45

    def test_independent_of_connect_timeout(self):
        executor = CodeExecutor(connect_timeout=15, kernel_init_timeout=60)
        assert executor.connect_timeout == 15
        assert executor.kernel_init_timeout == 60
