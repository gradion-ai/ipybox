import pytest
import pytest_asyncio

from ipybox import ExecutionClient, ExecutionContainer, ExecutionError
from ipybox.resource.client import ResourceClient


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def container_user(container_image_user: str):
    async with ExecutionContainer(tag=container_image_user) as container:
        yield container


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def container_root(container_image_root: str):
    async with ExecutionContainer(tag=container_image_root) as container:
        yield container


@pytest.mark.asyncio(loop_scope="module")
async def test_allowed_domain_access(container_user: ExecutionContainer):
    """Test that allowed domains are accessible after firewall init."""
    await container_user.init_firewall(["gradion.ai"])

    async with ExecutionClient(port=container_user.executor_port) as client:
        code = """import urllib.request
response = urllib.request.urlopen('https://gradion.ai', timeout=2)
print(response.read().decode('utf-8'))
"""
        result = await client.execute(code)

        assert "martin" in result.text.lower()
        assert "christoph" in result.text.lower()


@pytest.mark.asyncio(loop_scope="module")
async def test_allowed_ip_access(container_user: ExecutionContainer):
    """Test that an allowed IP address is accessible after firewall init."""
    await container_user.init_firewall(["8.8.8.8"])  # Google Public DNS

    async with ExecutionClient(port=container_user.executor_port) as client:
        code = """
import socket
s = socket.create_connection(('8.8.8.8', 53), timeout=3)
print('connected')
s.close()
"""
        result = await client.execute(code)
        assert "connected" in result.text


@pytest.mark.asyncio(loop_scope="module")
async def test_blocked_domain_access(container_user: ExecutionContainer):
    """Test that non-allowed domains are blocked with specific error."""
    await container_user.init_firewall(["gradion.ai"])

    async with ExecutionClient(port=container_user.executor_port) as client:
        code = """
import urllib.request
response = urllib.request.urlopen('https://example.com', timeout=2)
print(response.read().decode('utf-8'))
"""

        with pytest.raises(ExecutionError) as exc_info:
            await client.execute(code)

        assert "Network is unreachable" in str(exc_info.value)


@pytest.mark.asyncio(loop_scope="module")
async def test_empty_allowed_domains(container_user: ExecutionContainer):
    """Test firewall with empty allowed domains list."""
    await container_user.init_firewall([])

    async with ExecutionClient(port=container_user.executor_port) as client:
        code = """
import urllib.request
response = urllib.request.urlopen('https://example.com', timeout=2)
print(response.read().decode('utf-8'))
"""

        with pytest.raises(ExecutionError) as exc_info:
            await client.execute(code)

        assert "Network is unreachable" in str(exc_info.value)

        localhost_code = """
import urllib.request
response = urllib.request.urlopen('http://localhost:8900/status/', timeout=2)
print("Localhost accessible")
"""
        result = await client.execute(localhost_code)
        assert "Localhost accessible" in result.text


@pytest.mark.asyncio(loop_scope="module")
async def test_multiple_allowed_domains(container_user: ExecutionContainer):
    """Test firewall with multiple allowed domains."""
    await container_user.init_firewall(["gradion.ai", "httpbin.org", "api.github.com"])

    async with ExecutionClient(port=container_user.executor_port) as client:
        domains_to_test = [
            ("https://gradion.ai", "martin"),  # Check for expected content
            ("https://httpbin.org/get", "headers"),  # httpbin returns JSON with headers
            ("https://api.github.com/zen", None),  # GitHub API returns a zen quote
        ]

        for url, expected_content in domains_to_test:
            code = f"""
import urllib.request
response = urllib.request.urlopen('{url}', timeout=5)
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


@pytest.mark.asyncio(loop_scope="module")
async def test_firewall_fails_on_root_container(container_root: ExecutionContainer):
    """Test that firewall init fails on root container."""
    with pytest.raises(RuntimeError) as exc_info:
        await container_root.init_firewall()

    assert "container runs as root" in str(exc_info.value)


@pytest.mark.asyncio(loop_scope="module")
async def test_executor_works_after_firewall(container_user: ExecutionContainer):
    """Test that executor functionality remains after firewall init."""
    await container_user.init_firewall(["gradion.ai"])

    async with ExecutionClient(port=container_user.executor_port) as client:
        code = """
x = 42
print(f"The answer is {x}")
"""
        result = await client.execute(code)
        assert result.text == "The answer is 42"


@pytest.mark.asyncio(loop_scope="module")
async def test_resource_client_works_after_firewall(container_user: ExecutionContainer):
    """Test that resource client functionality remains after firewall init."""
    await container_user.init_firewall(["gradion.ai"])

    async with ResourceClient(port=container_user.resource_port) as resource_client:
        modules = await resource_client.get_module_sources(["ipybox.modinfo"])

        assert isinstance(modules, dict)
        assert "ipybox.modinfo" in modules
        assert len(modules["ipybox.modinfo"]) > 0


@pytest.mark.asyncio(loop_scope="module")
async def test_firewall_on_stopped_container():
    """Test init_firewall raises error when container not running."""
    container = ExecutionContainer()

    with pytest.raises(RuntimeError) as exc_info:
        await container.init_firewall()

    assert "Container not running" in str(exc_info.value)
