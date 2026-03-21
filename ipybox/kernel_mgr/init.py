import textwrap
from pathlib import Path

_ENV_SETUP = """\
import os as _os
%colors nocolor
for _k in ('CLICOLOR', 'CLICOLOR_FORCE', 'FORCE_COLOR'):
    _os.environ.pop(_k, None)
"""

_CWD_RESTORE = """\
_ipybox_cwd = {working_dir!r}
_os.chdir(_ipybox_cwd)
def _ipybox_restore_cwd(_result=None, _cwd=_ipybox_cwd, _os=_os):
    try:
        _current_cwd = _os.getcwd()
    except FileNotFoundError:
        _current_cwd = None
    if _current_cwd != _cwd:
        _os.chdir(_cwd)
        print(f'[ipybox] cwd reset to {{_cwd}}')
get_ipython().events.register('post_run_cell', _ipybox_restore_cwd)
del _ipybox_cwd, _ipybox_restore_cwd
"""

_SHELL_ESCAPE_GUARD = """\
from contextvars import ContextVar as _ContextVar
_ipybox_shell_allowed = _ContextVar('_ipybox_shell_allowed', default=False)
del _ContextVar
"""

_HANDLER_INSTALL = """\
_ip = get_ipython()
class _ipybox_safe_dict(dict):
    def __missing__(self, key):
        return '{{' + key + '}}'
def _ipybox_shell_handler(cmd, _run=_ip.system, _ns=_ip.user_ns, _SD=_ipybox_safe_dict):
{handler_body}
def _ipybox_getoutput_handler(cmd, _run=_ip.getoutput, _ns=_ip.user_ns, _SD=_ipybox_safe_dict):
{handler_body}
_ip.system = _ipybox_shell_handler
_ip.getoutput = _ipybox_getoutput_handler
del _ip, _ipybox_shell_handler, _ipybox_getoutput_handler, _ipybox_safe_dict
"""

_SUBPROCESS_GUARD = """\
import subprocess as _subprocess
_ipybox_orig_popen = _subprocess.Popen
class _ipybox_guarded_popen(_ipybox_orig_popen):
    def __init__(self, *args, **kwargs):
        if not _ipybox_shell_allowed.get():
            raise RuntimeError('Direct subprocess calls are not allowed. Use ! syntax.')
        super().__init__(*args, **kwargs)
_subprocess.Popen = _ipybox_guarded_popen
_ipybox_orig_os_system = _os.system
def _ipybox_guarded_os_system(cmd):
    if not _ipybox_shell_allowed.get():
        raise RuntimeError('Direct os.system() calls are not allowed. Use ! syntax.')
    return _ipybox_orig_os_system(cmd)
_os.system = _ipybox_guarded_os_system
del _subprocess, _ipybox_orig_popen, _ipybox_guarded_popen
del _ipybox_orig_os_system, _ipybox_guarded_os_system
for _ipybox_name in ('execv', 'execve', 'execl', 'execle', 'execvp', 'execvpe', 'execlp', 'execlpe',
                      'spawnv', 'spawnve', 'spawnvp', 'spawnvpe', 'spawnl', 'spawnle', 'spawnlp', 'spawnlpe',
                      'posix_spawn', 'posix_spawnp'):
    if hasattr(_os, _ipybox_name):
        _ipybox_orig = getattr(_os, _ipybox_name)
        def _ipybox_guard(*args, _orig=_ipybox_orig, _name=_ipybox_name, **kwargs):
            if not _ipybox_shell_allowed.get():
                raise RuntimeError(f'Direct os.{_name}() calls are not allowed. Use ! syntax.')
            return _orig(*args, **kwargs)
        setattr(_os, _ipybox_name, _ipybox_guard)
del _ipybox_name, _ipybox_orig, _ipybox_guard
try:
    import pty as _pty
    _ipybox_orig_pty_spawn = _pty.spawn
    def _ipybox_guarded_pty_spawn(*args, **kwargs):
        if not _ipybox_shell_allowed.get():
            raise RuntimeError('Direct pty.spawn() calls are not allowed. Use ! syntax.')
        return _ipybox_orig_pty_spawn(*args, **kwargs)
    _pty.spawn = _ipybox_guarded_pty_spawn
    del _pty, _ipybox_orig_pty_spawn, _ipybox_guarded_pty_spawn
except ImportError:
    pass
"""

_APPROVAL_HANDLER = """\
from mcpygen import ApprovalRequestor as _AR
_cmd = cmd.format_map(_SD(_ns))
_AR('ipybox', {host!r}, {port}).request_sync('shell', {{'cmd': _cmd}})
return _run(cmd)
"""

_APPROVAL_HANDLER_ESCAPE = """\
from mcpygen import ApprovalRequestor as _AR
_cmd = cmd.format_map(_SD(_ns))
_AR('ipybox', {host!r}, {port}).request_sync('shell', {{'cmd': _cmd}})
_ipybox_shell_allowed.set(True)
try:
    return _run(cmd)
finally:
    _ipybox_shell_allowed.set(False)
"""

_TERMINAL_ENV = """\
_os.environ['TERM'] = 'dumb'
_os.environ['NO_COLOR'] = '1'
del _os, _k
"""


def build_init_code(
    *,
    working_dir: Path | None = None,
    approve_shell_cmds: bool = False,
    require_shell_escape: bool = False,
    tool_server_host: str = "localhost",
    tool_server_port: int = 0,
) -> str:
    """Build the full kernel initialization code string.

    Args:
        working_dir: Working directory to restore after each cell execution.
        approve_shell_cmds: Whether to require approval for `!` shell
            commands via `ApprovalRequestor`.
        require_shell_escape: Whether to block direct process-creation
            calls (`subprocess`, `os.system`, `os.exec*`, `os.spawn*`,
            `os.posix_spawn*`, `pty.spawn`), forcing shell commands
            through the `!` handler. Requires `approve_shell_cmds=True`.
        tool_server_host: Hostname of the tool server (used when
            `approve_shell_cmds` is `True`).
        tool_server_port: Port of the tool server (used when
            `approve_shell_cmds` is `True`).
    """
    parts = [_ENV_SETUP]

    if working_dir is not None:
        parts.append(_CWD_RESTORE.format(working_dir=str(working_dir)))

    if approve_shell_cmds:
        if require_shell_escape:
            parts.append(_SHELL_ESCAPE_GUARD)
            handler = _APPROVAL_HANDLER_ESCAPE.format(host=tool_server_host, port=tool_server_port)
        else:
            handler = _APPROVAL_HANDLER.format(host=tool_server_host, port=tool_server_port)
        handler_body = textwrap.indent(handler.strip(), "    ")
        parts.append(_HANDLER_INSTALL.format(handler_body=handler_body))
        if require_shell_escape:
            parts.append(_SUBPROCESS_GUARD)

    parts.append(_TERMINAL_ENV)
    return "\n".join(parts)
