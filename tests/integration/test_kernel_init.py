"""Tests for kernel initialization behavior."""

import re

import pytest
import pytest_asyncio

from ipybox.kernel_mgr.client import ExecutionError, KernelClient
from ipybox.kernel_mgr.server import KernelGateway

ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")


@pytest_asyncio.fixture(scope="module")
async def gateway():
    async with KernelGateway(
        host="localhost",
        port=18888,
        log_level="WARNING",
    ) as gw:
        yield gw


@pytest_asyncio.fixture
async def client(gateway, tmp_path):
    async with KernelClient(
        host=gateway.host,
        port=gateway.port,
        images_dir=tmp_path / "images",
    ) as c:
        yield c


@pytest_asyncio.fixture
async def client_with_working_dir(gateway, tmp_path):
    async with KernelClient(
        host=gateway.host,
        port=gateway.port,
        working_dir=tmp_path,
        images_dir=tmp_path / "images",
    ) as c:
        yield c


class TestKernelInitialization:
    @pytest.mark.asyncio
    async def test_traceback_no_ansi(self, client: KernelClient):
        with pytest.raises(ExecutionError) as exc_info:
            await client.execute("1 / 0")
        error_msg = str(exc_info.value)
        assert "ZeroDivisionError" in error_msg
        assert not ANSI_ESCAPE.search(error_msg), f"Traceback contains ANSI:\n{error_msg!r}"

    @pytest.mark.asyncio
    async def test_ls_subprocess_no_ansi(self, client: KernelClient):
        result = await client.execute("import subprocess; print(subprocess.check_output(['ls', '-a']).decode())")
        assert result.text is not None
        assert not ANSI_ESCAPE.search(result.text), f"ls output contains ANSI:\n{result.text!r}"

    @pytest.mark.asyncio
    async def test_ls_shell_magic_no_ansi(self, client: KernelClient):
        result = await client.execute("!ls -a")
        assert result.text is not None
        assert not ANSI_ESCAPE.search(result.text), f"!ls -a output contains ANSI:\n{result.text!r}"

    @pytest.mark.asyncio
    async def test_init_does_not_leak_variables(self, client: KernelClient):
        for name in ("_os", "_k", "_ipybox_cwd", "_ipybox_restore_cwd"):
            with pytest.raises(ExecutionError) as exc_info:
                await client.execute(f"print({name})")
            assert "NameError" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_init_does_not_leak_hook_variables_with_working_dir(self, client_with_working_dir: KernelClient):
        for name in ("_os", "_k", "_ipybox_cwd", "_ipybox_restore_cwd"):
            with pytest.raises(ExecutionError) as exc_info:
                await client_with_working_dir.execute(f"print({name})")
            assert "NameError" in str(exc_info.value)
