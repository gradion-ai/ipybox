import sys
from pathlib import PurePath, PurePosixPath
from unittest.mock import patch

import pytest

from ipybox.modinfo import get_module_info


def test_get_module_info_regular_module():
    """Test getting module info for a regular module."""
    # Test with a standard library module
    module_info = get_module_info("os")

    assert module_info.name == "os"
    assert isinstance(module_info.relpath, PurePath)
    assert module_info.relpath == PurePosixPath("os.py")
    assert isinstance(module_info.source, str)
    assert len(module_info.source) > 0


def test_get_module_info_package_module():
    """Test getting module info for a module with __init__.py."""
    # Test with a package module (has __init__.py)
    module_info = get_module_info("ipybox")

    assert module_info.name == "ipybox"
    assert isinstance(module_info.relpath, PurePath)
    assert module_info.relpath == PurePosixPath("ipybox/__init__.py")
    assert isinstance(module_info.source, str)
    # We don't assert on content since some packages might have empty __init__.py files


def test_get_module_info_ipybox_module():
    """Test getting module info for ipybox's own module."""
    # Test with the modinfo module itself
    module_info = get_module_info("ipybox.modinfo")

    assert module_info.name == "ipybox.modinfo"
    assert isinstance(module_info.relpath, PurePath)
    assert module_info.relpath == PurePosixPath("ipybox/modinfo.py")
    assert isinstance(module_info.source, str)
    assert "get_module_info" in module_info.source


@pytest.fixture
def mock_module(tmp_path):
    """Create a mock module for testing."""
    module_dir = tmp_path / "mock_pkg"
    module_dir.mkdir()

    # Create an __init__.py file
    init_file = module_dir / "__init__.py"
    init_file.write_text("# Mock package init file")

    # Create a module file
    module_file = module_dir / "mock_module.py"
    module_file.write_text("def mock_function():\n    return 'mocked'")

    # Add to path so it can be imported
    sys.path.insert(0, str(tmp_path))

    yield "mock_pkg"

    # Cleanup
    sys.path.remove(str(tmp_path))

    # Remove from sys.modules if it was imported
    for mod_name in list(sys.modules.keys()):
        if mod_name.startswith("mock_pkg"):
            del sys.modules[mod_name]


def test_get_module_info_with_mock_module(mock_module):
    """Test getting module info using a mock module."""
    # Test with the mock package
    module_info = get_module_info(mock_module)

    assert module_info.name == mock_module
    assert isinstance(module_info.relpath, PurePath)
    assert module_info.relpath == PurePosixPath(f"{mock_module}/__init__.py")
    assert isinstance(module_info.source, str)
    assert "# Mock package init file" in module_info.source

    # Test with a submodule of the mock package
    submodule_name = f"{mock_module}.mock_module"
    submodule_info = get_module_info(submodule_name)

    assert submodule_info.name == submodule_name
    assert isinstance(submodule_info.relpath, PurePath)
    assert submodule_info.relpath == PurePosixPath(f"{mock_module}/mock_module.py")
    assert isinstance(submodule_info.source, str)
    assert "def mock_function()" in submodule_info.source


def test_nonexistent_module():
    """Test that importing a nonexistent module raises ModuleNotFoundError."""
    with pytest.raises(ModuleNotFoundError):
        get_module_info("nonexistent_module_that_doesnt_exist")


def test_get_module_info_handles_os_error():
    """Test that get_module_info handles OSError when getting source code."""
    with patch("ipybox.modinfo.getsource", side_effect=OSError("Mock OSError")):
        module_info = get_module_info("os")

        assert module_info.name == "os"
        assert isinstance(module_info.relpath, PurePath)
        assert module_info.relpath == PurePosixPath("os.py")
        assert isinstance(module_info.source, str)
        assert module_info.source == ""  # Source should be empty string due to OSError
