"""Unit tests for traceback rewriting."""

from ipybox.kernel_mgr.client import KernelClient


class TestRewriteTraceback:
    def test_drops_ipybox_prefixed_entries(self):
        entries = [
            "Traceback (most recent call last):",
            "  File ..., in _ipybox_shell_handler",
            "  File ..., in user_code",
        ]
        result = KernelClient._rewrite_traceback(entries)
        assert len(result) == 2
        assert "_ipybox_" not in result[1]

    def test_replaces_system_call_with_bang(self):
        entries = ["get_ipython().system('ls -la')"]
        result = KernelClient._rewrite_traceback(entries)
        assert result == ["!ls -la"]

    def test_replaces_getoutput_call_with_bang(self):
        entries = ['get_ipython().getoutput("echo hello")']
        result = KernelClient._rewrite_traceback(entries)
        assert result == ["!echo hello"]

    def test_preserves_unrelated_entries(self):
        entries = [
            "Traceback (most recent call last):",
            "  File 'user.py', line 1",
            "ValueError: bad input",
        ]
        result = KernelClient._rewrite_traceback(entries)
        assert result == entries

    def test_empty_input(self):
        assert KernelClient._rewrite_traceback([]) == []
