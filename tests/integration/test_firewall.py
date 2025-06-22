"""Integration tests for container firewall functionality."""

import pytest

from ipybox import ExecutionClient, ExecutionContainer, ExecutionError
from ipybox.resource.client import ResourceClient

# NOTE: Most tests create their own containers to avoid conflicts with the shared
# package-scoped container fixture that might have firewall already initialized


@pytest.mark.asyncio
async def test_allowed_domain_access(container_image_user: str):
    """Test that allowed domains are accessible after firewall init."""
    async with ExecutionContainer(tag=container_image_user) as container:
        # Initialize firewall with gradion.ai
        await container.init_firewall(["gradion.ai"])

        async with ExecutionClient(port=container.executor_port) as client:
            # Execute request to gradion.ai
            code = """
import urllib.request
response = urllib.request.urlopen('https://gradion.ai', timeout=2)
print(response.read().decode('utf-8'))
"""
            result = await client.execute(code)

            # Verify response contains "martin" and "christoph" (case-insensitive)
            assert "martin" in result.text.lower()
            assert "christoph" in result.text.lower()


@pytest.mark.asyncio
async def test_blocked_domain_access(container_image_user: str):
    """Test that non-allowed domains are blocked with specific error."""
    async with ExecutionContainer(tag=container_image_user) as container:
        # Initialize firewall with gradion.ai only
        await container.init_firewall(["gradion.ai"])

        async with ExecutionClient(port=container.executor_port) as client:
            # Execute request to example.com
            code = """
import urllib.request
response = urllib.request.urlopen('https://example.com', timeout=2)
print(response.read().decode('utf-8'))
"""

            # Verify ExecutionError with "Network is unreachable" message
            with pytest.raises(ExecutionError) as exc_info:
                await client.execute(code)

            assert "Network is unreachable" in str(exc_info.value)


@pytest.mark.asyncio
async def test_empty_allowed_domains(container_image_user: str):
    """Test firewall with empty allowed domains list."""
    async with ExecutionContainer(tag=container_image_user) as container:
        # Initialize firewall with []
        await container.init_firewall([])

        async with ExecutionClient(port=container.executor_port) as client:
            # Verify all external domains are blocked
            code = """
import urllib.request
response = urllib.request.urlopen('https://example.com', timeout=2)
print(response.read().decode('utf-8'))
"""

            with pytest.raises(ExecutionError) as exc_info:
                await client.execute(code)

            assert "Network is unreachable" in str(exc_info.value)

            # Verify localhost still works
            localhost_code = """
import urllib.request
response = urllib.request.urlopen('http://localhost:8900/status/', timeout=2)
print("Localhost accessible")
"""
            result = await client.execute(localhost_code)
            assert "Localhost accessible" in result.text


@pytest.mark.asyncio
async def test_multiple_allowed_domains(container_image_user: str):
    """Test firewall with multiple allowed domains."""
    async with ExecutionContainer(tag=container_image_user) as container:
        # Initialize firewall with ["gradion.ai", "httpbin.org", "api.github.com"]
        await container.init_firewall(["gradion.ai", "httpbin.org", "api.github.com"])

        async with ExecutionClient(port=container.executor_port) as client:
            # Test access to each domain
            domains_to_test = [
                ("https://gradion.ai", "martin"),  # Check for expected content
                ("https://httpbin.org/get", "headers"),  # httpbin returns JSON with headers
                ("https://api.github.com/zen", None),  # GitHub API returns a zen quote
            ]

            for url, expected_content in domains_to_test:
                code = f"""
import urllib.request
response = urllib.request.urlopen('{url}', timeout=3)
print(response.read().decode('utf-8'))
"""
                result = await client.execute(code)
                if expected_content:
                    assert expected_content in result.text.lower()

            # Verify non-listed domains are blocked
            blocked_code = """
import urllib.request
response = urllib.request.urlopen('https://example.com', timeout=2)
print(response.read().decode('utf-8'))
"""

            with pytest.raises(ExecutionError) as exc_info:
                await client.execute(blocked_code)

            assert "Network is unreachable" in str(exc_info.value)


@pytest.mark.asyncio
async def test_firewall_fails_on_root_container(container_image_root: str):
    """Test that firewall init fails on root container."""
    # Create container with test-root image
    async with ExecutionContainer(tag=container_image_root) as container:
        # Call init_firewall()
        # Verify RuntimeError with "container runs as root" message
        with pytest.raises(RuntimeError) as exc_info:
            await container.init_firewall()

        assert "container runs as root" in str(exc_info.value)


@pytest.mark.asyncio
async def test_executor_works_after_firewall(container_image_user: str):
    """Test that executor functionality remains after firewall init."""
    async with ExecutionContainer(tag=container_image_user) as container:
        # Initialize firewall
        await container.init_firewall(["gradion.ai"])

        async with ExecutionClient(port=container.executor_port) as client:
            # Execute simple code
            code = """
x = 42
print(f"The answer is {x}")
"""
            result = await client.execute(code)

            # Verify execution works
            assert result.text == "The answer is 42"


@pytest.mark.asyncio
async def test_resource_client_works_after_firewall(container_image_user: str):
    """Test that resource client functionality remains after firewall init."""
    async with ExecutionContainer(tag=container_image_user) as container:
        # Initialize firewall
        await container.init_firewall(["gradion.ai"])

        # Call get_module_sources()
        async with ResourceClient(port=container.resource_port) as resource_client:
            modules = await resource_client.get_module_sources(["ipybox.modinfo"])

            # Verify it returns results
            assert isinstance(modules, dict)
            assert "ipybox.modinfo" in modules
            assert len(modules["ipybox.modinfo"]) > 0


@pytest.mark.asyncio
async def test_firewall_on_stopped_container():
    """Test init_firewall raises error when container not running."""
    # Create container but don't start it
    container = ExecutionContainer()

    # Call init_firewall()
    # Verify RuntimeError "Container not running"
    with pytest.raises(RuntimeError) as exc_info:
        await container.init_firewall()

    assert "Container not running" in str(exc_info.value)


@pytest.mark.asyncio
async def test_firewall_with_fresh_container(container_image_user: str):
    """Test firewall initialization with a fresh container."""
    # Create and run a fresh container
    async with ExecutionContainer(tag=container_image_user) as container:
        # Initialize firewall
        await container.init_firewall(["gradion.ai"])

        # Create execution client and test
        async with ExecutionClient(port=container.executor_port) as client:
            # Test simple execution works
            result = await client.execute("print('Firewall initialized!')")
            assert result.text == "Firewall initialized!"

            # Test allowed domain access
            code = """
import urllib.request, urllib.error
try:
    response = urllib.request.urlopen('https://gradion.ai', timeout=2)
    print('SUCCESS: Reached gradion.ai')
except Exception as e:
    print(f'FAILED: {e}')
"""
            result = await client.execute(code)
            assert "SUCCESS" in result.text


@pytest.mark.asyncio
async def test_connection_error_format(container_image_user: str):
    """Test the specific format of connection errors when blocked."""
    async with ExecutionContainer(tag=container_image_user) as container:
        # Initialize firewall without example.com
        await container.init_firewall([])

        async with ExecutionClient(port=container.executor_port) as client:
            # Try to access example.com
            code = """
import urllib.request
response = urllib.request.urlopen('https://example.com', timeout=2)
print(response.read().decode('utf-8'))
"""

            # Verify error contains "URLError" and "Network is unreachable"
            with pytest.raises(ExecutionError) as exc_info:
                await client.execute(code)

            error_str = str(exc_info.value)
            assert "URLError" in error_str
            assert "Network is unreachable" in error_str
