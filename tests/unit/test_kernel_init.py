"""Unit tests for kernel initialization code generation."""

from pathlib import Path

from ipybox.kernel_mgr.init import build_init_code


class TestBuildInitCodeBase:
    """Tests for the base init code (always present)."""

    def test_always_includes_env_setup(self):
        code = build_init_code()
        assert "import os as _os" in code
        assert "%colors nocolor" in code

    def test_always_includes_terminal_env(self):
        code = build_init_code()
        assert "_os.environ['TERM'] = 'dumb'" in code
        assert "_os.environ['NO_COLOR'] = '1'" in code

    def test_always_cleans_up_variables(self):
        code = build_init_code()
        assert "del _os, _k" in code

    def test_no_handler_by_default(self):
        code = build_init_code()
        assert "_ipybox_shell_handler" not in code
        assert "ApprovalRequestor" not in code


class TestBuildInitCodeWorkingDir:
    """Tests for the working directory restore hook."""

    def test_includes_cwd_restore_hook(self):
        code = build_init_code(working_dir=Path("/test/dir"))
        assert "_ipybox_cwd = '/test/dir'" in code
        assert "_os.chdir(_ipybox_cwd)" in code
        assert "post_run_cell" in code

    def test_cleans_up_hook_variables(self):
        code = build_init_code(working_dir=Path("/test/dir"))
        assert "del _ipybox_cwd, _ipybox_restore_cwd" in code

    def test_no_cwd_hook_without_working_dir(self):
        code = build_init_code()
        assert "_ipybox_cwd" not in code
        assert "_ipybox_restore_cwd" not in code


class TestBuildInitCodeApproval:
    """Tests for the shell command approval handler."""

    def test_installs_handler(self):
        code = build_init_code(
            approve_shell_cmds=True,
            tool_server_host="myhost",
            tool_server_port=9999,
        )
        assert "_ipybox_shell_handler" in code
        assert "_ipybox_getoutput_handler" in code
        assert "_ip.system = _ipybox_shell_handler" in code
        assert "_ip.getoutput = _ipybox_getoutput_handler" in code

    def test_handler_contains_approval_requestor(self):
        code = build_init_code(
            approve_shell_cmds=True,
            tool_server_host="myhost",
            tool_server_port=9999,
        )
        assert "ApprovalRequestor" in code
        assert "'myhost'" in code
        assert "9999" in code

    def test_handler_calls_run(self):
        code = build_init_code(approve_shell_cmds=True)
        assert "return _run(cmd)" in code

    def test_cleans_up_handler_variables(self):
        code = build_init_code(approve_shell_cmds=True)
        assert "del _ip, _ipybox_shell_handler, _ipybox_getoutput_handler" in code


class TestBuildInitCodeShellEscape:
    """Tests for the require_shell_escape guard."""

    def test_includes_context_var_guard(self):
        code = build_init_code(approve_shell_cmds=True, require_shell_escape=True)
        assert "_ipybox_shell_allowed" in code
        assert "ContextVar" in code

    def test_guards_subprocess_popen(self):
        code = build_init_code(approve_shell_cmds=True, require_shell_escape=True)
        assert "_ipybox_guarded_popen" in code
        assert "_subprocess.Popen = _ipybox_guarded_popen" in code
        assert "Direct subprocess calls are not allowed" in code

    def test_guards_os_system(self):
        code = build_init_code(approve_shell_cmds=True, require_shell_escape=True)
        assert "_ipybox_guarded_os_system" in code
        assert "_os.system = _ipybox_guarded_os_system" in code
        assert "Direct os.system() calls are not allowed" in code

    def test_handler_sets_shell_allowed(self):
        code = build_init_code(approve_shell_cmds=True, require_shell_escape=True)
        assert "_ipybox_shell_allowed.set(True)" in code
        assert "_ipybox_shell_allowed.set(False)" in code

    def test_no_guard_without_require_shell_escape(self):
        code = build_init_code(approve_shell_cmds=True, require_shell_escape=False)
        assert "_ipybox_shell_allowed" not in code
        assert "_ipybox_guarded_popen" not in code

    def test_no_guard_without_approve_shell_cmds(self):
        code = build_init_code(require_shell_escape=True)
        assert "_ipybox_shell_allowed" not in code
        assert "_ipybox_guarded_popen" not in code
