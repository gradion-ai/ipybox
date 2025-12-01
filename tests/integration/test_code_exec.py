import asyncio
import json
import sys
from pathlib import Path

import pytest
import pytest_asyncio

from ipybox.code_exec.client import ExecutionError, ExecutionResult, KernelClient
from ipybox.code_exec.server import KernelGateway


@pytest_asyncio.fixture(scope="module")
async def kernel_gateway():
    async with KernelGateway(
        host="localhost",
        port=8888,
        log_level="WARNING",
        env={"TEST_VAR": "test_val"},
    ) as gateway:
        yield gateway


@pytest_asyncio.fixture(scope="class")
async def kernel_gateway_default_sandbox():
    """Gateway with default sandbox config (no network access)."""
    async with KernelGateway(
        host="localhost",
        port=8889,
        log_level="WARNING",
        sandbox=True,
    ) as gateway:
        yield gateway


@pytest_asyncio.fixture(scope="class")
async def kernel_gateway_custom_sandbox():
    """Gateway with custom sandbox config (httpbin.org allowed)."""
    async with KernelGateway(
        host="localhost",
        port=8890,
        log_level="WARNING",
        sandbox=True,
        sandbox_config=Path("tests/integration/sandbox.json"),
    ) as gateway:
        yield gateway


@pytest_asyncio.fixture
async def kernel_client(kernel_gateway, tmp_path):
    async with KernelClient(
        host=kernel_gateway.host,
        port=kernel_gateway.port,
        images_dir=tmp_path / "images",
    ) as client:
        yield client


class TestBasicExecution:
    """Tests for basic code execution functionality."""

    @pytest.mark.asyncio
    async def test_execute_simple_print(self, kernel_client: KernelClient):
        """Test simple print statement execution."""
        result = await kernel_client.execute("print('Hello')")
        assert result.text == "Hello"
        assert result.images == []

    @pytest.mark.asyncio
    async def test_execute_arithmetic(self, kernel_client: KernelClient):
        """Test arithmetic expression execution."""
        result = await kernel_client.execute("2 + 2")
        assert result.text == "4"
        assert result.images == []

    @pytest.mark.asyncio
    async def test_execute_multiline_code(self, kernel_client: KernelClient):
        """Test multiline code execution."""
        code = """
x = 5
y = 10
x + y
"""
        result = await kernel_client.execute(code)
        assert result.text == "15"

    @pytest.mark.asyncio
    async def test_execute_no_output(self, kernel_client: KernelClient):
        """Test code with no output returns None text."""
        result = await kernel_client.execute("x = 42")
        assert result.text is None
        assert result.images == []

    @pytest.mark.asyncio
    async def test_execute_multiple_outputs(self, kernel_client: KernelClient):
        """Test multiple print statements are combined."""
        code = """
print('first')
print('second')
print('third')
"""
        result = await kernel_client.execute(code)
        assert result.text is not None
        assert "first" in result.text
        assert "second" in result.text
        assert "third" in result.text

    @pytest.mark.asyncio
    async def test_execute_empty_code(self, kernel_client: KernelClient):
        """Test empty code returns None text."""
        result = await kernel_client.execute("")
        assert result.text is None
        assert result.images == []


class TestErrorHandling:
    """Tests for error handling in code execution."""

    @pytest.mark.asyncio
    async def test_execute_syntax_error(self, kernel_client: KernelClient):
        """Test syntax errors raise ExecutionError."""
        with pytest.raises(ExecutionError) as exc_info:
            await kernel_client.execute("print('missing quote)")
        assert "SyntaxError" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_execute_runtime_error(self, kernel_client: KernelClient):
        """Test runtime errors raise ExecutionError."""
        with pytest.raises(ExecutionError) as exc_info:
            await kernel_client.execute("1 / 0")
        assert "ZeroDivisionError" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_execute_name_error(self, kernel_client: KernelClient):
        """Test undefined variable raises ExecutionError."""
        with pytest.raises(ExecutionError) as exc_info:
            await kernel_client.execute("print(undefined_variable)")
        assert "NameError" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_error_includes_traceback(self, kernel_client: KernelClient):
        """Test error messages include stack trace."""
        with pytest.raises(ExecutionError) as exc_info:
            code = """
def foo():
    return 1 / 0

foo()
"""
            await kernel_client.execute(code)
        error_msg = str(exc_info.value)
        assert "ZeroDivisionError" in error_msg
        assert "foo" in error_msg

    @pytest.mark.asyncio
    async def test_stream_raises_error(self, kernel_client: KernelClient):
        """Test streaming also raises ExecutionError."""
        with pytest.raises(ExecutionError) as exc_info:
            async for _ in kernel_client.stream("1 / 0"):
                pass
        assert "ZeroDivisionError" in str(exc_info.value)


class TestStreaming:
    """Tests for streaming functionality."""

    @pytest.mark.asyncio
    async def test_stream_outputs_incrementally(self, kernel_client: KernelClient):
        """Test chunks are yielded as generated."""
        code = """
import time
print('first')
time.sleep(0.5)
print('second')
"""
        chunks = []
        async for item in kernel_client.stream(code):
            if isinstance(item, str):
                chunks.append(item)

        # Verify we got exactly 2 chunks (one per print statement)
        assert len(chunks) == 2
        assert chunks[0] == "first\n"
        assert chunks[1] == "second\n"

    @pytest.mark.asyncio
    async def test_stream_yields_final_result(self, kernel_client: KernelClient):
        """Test stream yields ExecutionResult as final item."""
        items = []
        async for item in kernel_client.stream("print('hello')"):
            items.append(item)

        # Last item should be ExecutionResult
        assert len(items) >= 1
        assert isinstance(items[-1], ExecutionResult)
        assert items[-1].text == "hello"

    @pytest.mark.asyncio
    async def test_stream_mixed_output(self, kernel_client: KernelClient):
        """Test streaming with both chunks and final result."""
        code = """
import time
print('chunk1')
time.sleep(0.5)
print('chunk2')
"""
        str_chunks = []
        result = None
        async for item in kernel_client.stream(code):
            if isinstance(item, str):
                str_chunks.append(item)
            elif isinstance(item, ExecutionResult):
                result = item

        assert str_chunks == ["chunk1\n", "chunk2\n"]
        assert result is not None
        assert result.text == "chunk1\nchunk2"


class TestStatePersistence:
    """Tests for state persistence across executions."""

    @pytest.mark.asyncio
    async def test_variable_persists_across_executions(self, kernel_client: KernelClient):
        """Test variables persist between executions."""
        await kernel_client.execute("x = 42")
        result = await kernel_client.execute("print(x)")
        assert result.text == "42"

    @pytest.mark.asyncio
    async def test_function_definition_persists(self, kernel_client: KernelClient):
        """Test function definitions persist."""
        await kernel_client.execute("def add(a, b): return a + b")
        result = await kernel_client.execute("add(10, 20)")
        assert result.text == "30"

    @pytest.mark.asyncio
    async def test_import_persists(self, kernel_client: KernelClient):
        """Test imports persist between executions."""
        await kernel_client.execute("import math")
        result = await kernel_client.execute("math.pi")
        assert result.text is not None
        assert "3.14" in result.text

    @pytest.mark.asyncio
    async def test_state_isolation_between_clients(self, kernel_gateway):
        """Test different clients have isolated state."""
        # Use inline context managers for separate clients
        async with KernelClient(host=kernel_gateway.host, port=kernel_gateway.port) as client1:
            await client1.execute("isolated_var = 'client1'")

        async with KernelClient(host=kernel_gateway.host, port=kernel_gateway.port) as client2:
            with pytest.raises(ExecutionError) as exc_info:
                await client2.execute("print(isolated_var)")
            assert "NameError" in str(exc_info.value)


class TestImageGeneration:
    """Tests for matplotlib image generation."""

    @pytest.mark.asyncio
    async def test_execute_matplotlib_plot(self, kernel_client: KernelClient):
        """Test matplotlib generates PNG image."""
        code = """
import matplotlib.pyplot as plt
plt.plot([1, 2, 3], [4, 5, 6])
plt.show()
"""
        result = await kernel_client.execute(code)
        assert len(result.images) == 1
        assert result.images[0].exists()
        assert result.images[0].suffix == ".png"

    @pytest.mark.asyncio
    async def test_execute_multiple_plots(self, kernel_client: KernelClient):
        """Test multiple plots return multiple images."""
        code = """
import matplotlib.pyplot as plt

plt.plot([1, 2, 3], [4, 5, 6])
plt.show()

plt.plot([4, 5, 6], [1, 2, 3])
plt.show()
"""
        result = await kernel_client.execute(code)
        assert len(result.images) == 2
        assert all(img.exists() for img in result.images)
        assert all(img.suffix == ".png" for img in result.images)

    @pytest.mark.asyncio
    async def test_images_saved_to_images_dir(self, kernel_client: KernelClient):
        """Test images are saved to correct directory."""
        code = """
import matplotlib.pyplot as plt
plt.plot([1, 2, 3], [4, 5, 6])
plt.show()
"""
        result = await kernel_client.execute(code)
        assert len(result.images) == 1
        assert result.images[0].parent == kernel_client.images_dir


class TestTimeouts:
    """Tests for timeout handling."""

    @pytest.mark.asyncio
    async def test_execute_timeout(self, kernel_client: KernelClient):
        """Test long-running code raises asyncio.TimeoutError."""
        code = "import time; time.sleep(10)"
        with pytest.raises(asyncio.TimeoutError):
            await kernel_client.execute(code, timeout=0.5)

    @pytest.mark.asyncio
    async def test_execution_continues_after_timeout(self, kernel_client: KernelClient):
        """Test client is usable after timeout."""
        # Trigger timeout
        code = "import time; time.sleep(10)"
        with pytest.raises(asyncio.TimeoutError):
            await kernel_client.execute(code, timeout=0.5)

        # Wait a bit for kernel to recover
        await asyncio.sleep(0.5)

        # Client should still be usable
        result = await kernel_client.execute("print('recovered')")
        assert result.text == "recovered"

    @pytest.mark.asyncio
    async def test_kernel_state_preserved_after_interrupt(self, kernel_client: KernelClient):
        """Test that variable state is preserved after kernel interrupt."""
        code = """
a = 0
while True:
    a = 5
"""
        with pytest.raises(asyncio.TimeoutError):
            await kernel_client.execute(code, timeout=1.0)

        # Wait for kernel to recover
        await asyncio.sleep(0.5)

        # Verify variable was set before interrupt
        result = await kernel_client.execute("print(a)")
        assert result.text == "5"


class TestScaling:
    """Tests for handling large inputs, outputs, and many chunks."""

    @pytest.mark.asyncio
    async def test_execute_large_output(self, kernel_client: KernelClient):
        """Test handling of very large single-line output."""
        result = await kernel_client.execute("print('a' * 500000)")
        assert result.text == "a" * 500000

    @pytest.mark.asyncio
    async def test_execute_large_multiline_output(self, kernel_client: KernelClient):
        """Test handling of very large multiline output."""
        result = await kernel_client.execute("s = 'a\\n' * 50000; print(s)")
        assert result.text == ("a\n" * 50000).strip()

    @pytest.mark.asyncio
    async def test_execute_large_input(self, kernel_client: KernelClient):
        """Test handling of very large code input."""
        code = "result = 0\n"
        code += "\n".join(f"result += {i}" for i in range(10000))
        code += "\nprint(result)"
        result = await kernel_client.execute(code)
        assert result.text == str(sum(range(10000)))

    @pytest.mark.asyncio
    async def test_execute_chunked_output(self, kernel_client: KernelClient):
        """Test handling of many small output chunks over time."""
        code = """
import asyncio

for i in range(100):
    print("a")
    await asyncio.sleep(0.01)
"""
        result = await kernel_client.execute(code)
        assert result.text == ("a\n" * 100).strip()


class TestEnvironment:
    """Tests for environment variable support."""

    @pytest.mark.asyncio
    async def test_execute_with_custom_environment_variable(self, kernel_client: KernelClient):
        """Test that custom environment variables are accessible in kernel."""
        result = await kernel_client.execute("import os; print(os.environ['TEST_VAR'])")
        assert result.text == "test_val"


@pytest.mark.skipif(sys.platform != "darwin", reason="Sandbox tests only run on macOS")
class TestSandbox:
    """Tests for sandbox network isolation."""

    HTTP_CODE = """
import urllib.request
response = urllib.request.urlopen('https://httpbin.org/get')
content = response.read().decode('utf-8')
print(content)
"""

    @pytest.mark.asyncio
    async def test_default_sandbox_blocks_network(self, kernel_gateway_default_sandbox):
        """Test that default sandbox config blocks all network access."""
        async with KernelClient(
            host=kernel_gateway_default_sandbox.host,
            port=kernel_gateway_default_sandbox.port,
        ) as client:
            with pytest.raises(ExecutionError) as exc_info:
                await client.execute(self.HTTP_CODE)
            assert "URLError" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_custom_sandbox_allows_httpbin(self, kernel_gateway_custom_sandbox):
        """Test that custom sandbox config allows httpbin.org access."""
        async with KernelClient(
            host=kernel_gateway_custom_sandbox.host,
            port=kernel_gateway_custom_sandbox.port,
        ) as client:
            result = await client.execute(self.HTTP_CODE)
            assert result.text is not None
            data = json.loads(result.text)
            assert data["url"] == "https://httpbin.org/get"
            assert data["headers"]["Host"] == "httpbin.org"
