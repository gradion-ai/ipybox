"""Integration tests for shell command approval and shell escape."""

import pytest
import pytest_asyncio

from ipybox import (
    ApprovalRequest,
    CodeExecutionError,
    CodeExecutionResult,
    CodeExecutor,
)


@pytest_asyncio.fixture
async def executor_approve():
    async with CodeExecutor(
        approve_shell_cmds=True,
        log_level="ERROR",
    ) as executor:
        yield executor


@pytest_asyncio.fixture
async def executor_escape():
    async with CodeExecutor(
        approve_shell_cmds=True,
        require_shell_escape=True,
        log_level="ERROR",
    ) as executor:
        yield executor


class TestApproveShellCmds:
    @pytest.mark.asyncio
    async def test_shell_cmd_triggers_approval(self, executor_approve: CodeExecutor):
        approvals = []
        async for item in executor_approve.stream("!echo hello"):
            match item:
                case ApprovalRequest():
                    approvals.append(item)
                    await item.accept()
                case CodeExecutionResult():
                    result = item

        assert len(approvals) == 1
        assert approvals[0].tool_name == "shell"
        assert "echo hello" in approvals[0].tool_args["cmd"]
        assert result.text is not None
        assert "hello" in result.text

    @pytest.mark.asyncio
    async def test_shell_cmd_with_variable_substitution(self, executor_approve: CodeExecutor):
        code = "x = 'world'\n!echo {x}"
        approvals = []
        async for item in executor_approve.stream(code):
            match item:
                case ApprovalRequest():
                    approvals.append(item)
                    await item.accept()
                case CodeExecutionResult():
                    pass

        assert len(approvals) == 1
        assert "world" in approvals[0].tool_args["cmd"]

    @pytest.mark.asyncio
    async def test_getoutput_triggers_approval(self, executor_approve: CodeExecutor):
        code = "result = !echo captured\nprint(result)"
        approvals = []
        async for item in executor_approve.stream(code):
            match item:
                case ApprovalRequest():
                    approvals.append(item)
                    await item.accept()
                case CodeExecutionResult():
                    result = item

        assert len(approvals) == 1
        assert result.text is not None
        assert "captured" in result.text

    @pytest.mark.asyncio
    async def test_multiple_shell_cmds_trigger_multiple_approvals(self, executor_approve: CodeExecutor):
        code = "!echo one\n!echo two"
        approvals = []
        async for item in executor_approve.stream(code):
            match item:
                case ApprovalRequest():
                    approvals.append(item)
                    await item.accept()
                case CodeExecutionResult():
                    pass

        assert len(approvals) == 2

    @pytest.mark.asyncio
    async def test_init_does_not_leak_handler_variables(self, executor_approve: CodeExecutor):
        for name in (
            "_ip",
            "_ipybox_shell_handler",
            "_ipybox_getoutput_handler",
            "_ipybox_safe_dict",
        ):
            with pytest.raises(CodeExecutionError) as exc_info:
                await executor_approve.execute(f"print({name})")
            assert "NameError" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_shell_cmd_rejection(self, executor_approve: CodeExecutor):
        with pytest.raises(CodeExecutionError) as exc_info:
            async for item in executor_approve.stream("!echo secret"):
                match item:
                    case ApprovalRequest():
                        await item.reject()

        assert "Rejected" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_shell_cmd_with_undefined_variable(self, executor_approve: CodeExecutor):
        approvals = []
        async for item in executor_approve.stream("!echo {undefined_var}"):
            match item:
                case ApprovalRequest():
                    approvals.append(item)
                    await item.accept()
                case CodeExecutionResult():
                    pass

        assert len(approvals) == 1
        assert "{undefined_var}" in approvals[0].tool_args["cmd"]


class TestRequireShellEscape:
    @pytest.mark.asyncio
    async def test_subprocess_run_blocked(self, executor_escape: CodeExecutor):
        with pytest.raises(CodeExecutionError) as exc_info:
            await executor_escape.execute('import subprocess; subprocess.run(["echo", "hi"])')
        assert "Direct subprocess calls are not allowed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_subprocess_popen_blocked(self, executor_escape: CodeExecutor):
        with pytest.raises(CodeExecutionError) as exc_info:
            await executor_escape.execute('import subprocess; subprocess.Popen(["echo", "hi"]).wait()')
        assert "Direct subprocess calls are not allowed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_os_system_blocked(self, executor_escape: CodeExecutor):
        with pytest.raises(CodeExecutionError) as exc_info:
            await executor_escape.execute('import os; os.system("echo hi")')
        assert "Direct os.system() calls are not allowed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_os_execvp_blocked(self, executor_escape: CodeExecutor):
        with pytest.raises(CodeExecutionError) as exc_info:
            await executor_escape.execute('import os; os.execvp("echo", ["echo", "hi"])')
        assert "Direct os.execvp() calls are not allowed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_os_spawnl_blocked(self, executor_escape: CodeExecutor):
        with pytest.raises(CodeExecutionError) as exc_info:
            await executor_escape.execute('import os; os.spawnl(os.P_WAIT, "/bin/echo", "echo", "hi")')
        assert "Direct os.spawnl() calls are not allowed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_os_posix_spawn_blocked(self, executor_escape: CodeExecutor):
        with pytest.raises(CodeExecutionError) as exc_info:
            await executor_escape.execute('import os; os.posix_spawn("/bin/echo", ["/bin/echo", "hi"], os.environ)')
        assert "Direct os.posix_spawn() calls are not allowed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_pty_spawn_blocked(self, executor_escape: CodeExecutor):
        with pytest.raises(CodeExecutionError) as exc_info:
            await executor_escape.execute('import pty; pty.spawn(["/bin/echo", "hi"])')
        assert "Direct pty.spawn() calls are not allowed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_shell_cmd_still_works(self, executor_escape: CodeExecutor):
        approvals = []
        async for item in executor_escape.stream("!echo hello"):
            match item:
                case ApprovalRequest():
                    approvals.append(item)
                    await item.accept()
                case CodeExecutionResult():
                    result = item

        assert len(approvals) == 1
        assert result.text is not None
        assert "hello" in result.text

    @pytest.mark.asyncio
    async def test_init_does_not_leak_guard_variables(self, executor_escape: CodeExecutor):
        for name in (
            "_ipybox_guarded_popen",
            "_ipybox_guarded_os_system",
            "_ipybox_orig_popen",
            "_ipybox_orig_os_system",
            "_ipybox_guard",
            "_ipybox_name",
            "_ipybox_orig",
            "_ipybox_orig_pty_spawn",
            "_ipybox_guarded_pty_spawn",
        ):
            with pytest.raises(CodeExecutionError) as exc_info:
                await executor_escape.execute(f"print({name})")
            assert "NameError" in str(exc_info.value)
