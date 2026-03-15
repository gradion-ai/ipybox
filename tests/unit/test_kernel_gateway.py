import asyncio
from types import SimpleNamespace

import pytest

from ipybox.kernel_mgr.server import KernelGateway


@pytest.mark.asyncio
async def test_start_discards_stdio_when_log_to_stderr_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    async def fake_create_subprocess_exec(*cmd: object, **kwargs: object) -> SimpleNamespace:
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return SimpleNamespace(returncode=0, pid=123)

    monkeypatch.setattr("ipybox.kernel_mgr.server.asyncio.create_subprocess_exec", fake_create_subprocess_exec)

    gateway = KernelGateway(host="127.0.0.1", port=9999, log_level="ERROR")
    await gateway.start()

    kwargs = captured["kwargs"]
    assert isinstance(kwargs, dict)
    assert kwargs["stdout"] is asyncio.subprocess.DEVNULL
    assert kwargs["stderr"] is asyncio.subprocess.DEVNULL


@pytest.mark.asyncio
async def test_start_uses_configured_working_dir(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    captured: dict[str, object] = {}

    async def fake_create_subprocess_exec(*cmd: object, **kwargs: object) -> SimpleNamespace:
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return SimpleNamespace(returncode=0, pid=123)

    monkeypatch.setattr("ipybox.kernel_mgr.server.asyncio.create_subprocess_exec", fake_create_subprocess_exec)

    gateway = KernelGateway(host="127.0.0.1", port=9999, working_dir=tmp_path, log_level="ERROR")
    await gateway.start()

    kwargs = captured["kwargs"]
    assert isinstance(kwargs, dict)
    assert kwargs["cwd"] == tmp_path.resolve()
