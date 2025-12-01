import json
import sys
import tempfile
from pathlib import Path

import pytest
import pytest_asyncio

from ipybox import ApprovalRequest, CodeExecutionChunk, CodeExecutionError, CodeExecutionResult, CodeExecutor
from ipybox.mcp_apigen import generate_mcp_sources
from tests.integration.mcp_server import STDIO_SERVER_PATH

MCP_SERVER_NAME = "test_mcp"


@pytest_asyncio.fixture(scope="module")
async def generated_mcp_package():
    """Generate MCP wrapper sources to a temp directory."""
    server_params = {
        "command": "python",
        "args": [str(STDIO_SERVER_PATH)],
    }

    with tempfile.TemporaryDirectory() as tmp_dir:
        root_dir = Path(tmp_dir)

        tool_names = await generate_mcp_sources(
            server_name=MCP_SERVER_NAME,
            server_params=server_params,
            root_dir=root_dir,
        )

        yield {
            "root_dir": root_dir,
            "package_dir": root_dir / MCP_SERVER_NAME,
            "tool_names": tool_names,
            "server_params": server_params,
        }


@pytest_asyncio.fixture
async def code_executor(generated_mcp_package: dict):
    """Create a CodeExecutor with access to generated MCP package."""
    root_dir = generated_mcp_package["root_dir"]

    async with CodeExecutor(
        kernel_env={"PYTHONPATH": str(root_dir)},
        log_level="WARNING",
    ) as executor:
        yield executor


class TestBasicExecution:
    """Basic facade functionality without MCP tools."""

    @pytest.mark.asyncio
    async def test_simple_code_execution(self, code_executor: CodeExecutor):
        """Test executing a simple print statement."""
        code = "print('hello world')"

        results = []
        async for item in code_executor.execute(code):
            results.append(item)

        assert len(results) == 1
        assert isinstance(results[0], CodeExecutionResult)
        assert results[0].text == "hello world"

    @pytest.mark.asyncio
    async def test_code_execution_error(self, code_executor: CodeExecutor):
        """Test that CodeExecutionError is raised on runtime error."""
        code = "raise ValueError('test error')"

        with pytest.raises(CodeExecutionError) as exc_info:
            async for _ in code_executor.execute(code):
                pass

        assert "ValueError" in str(exc_info.value)
        assert "test error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_streaming_execution(self, code_executor: CodeExecutor):
        """Test that CodeExecutionChunk is yielded when stream=True."""
        code = """
import time
for i in range(3):
    print(f'chunk {i}', flush=True)
    time.sleep(0.05)
"""

        chunks = []
        result = None
        async for item in code_executor.execute(code, stream=True):
            match item:
                case CodeExecutionChunk():
                    chunks.append(item)
                case CodeExecutionResult():
                    result = item

        assert len(chunks) > 0
        combined_text = "".join(c.text for c in chunks)
        assert "chunk 0" in combined_text
        assert "chunk 1" in combined_text
        assert "chunk 2" in combined_text
        assert result is not None


class TestMcpToolExecution:
    """Core integration: kernel code calling MCP tools through approval."""

    @pytest.mark.asyncio
    async def test_tool_call_with_approval_accepted(self, code_executor: CodeExecutor):
        """Test calling a tool and accepting the approval request."""
        code = f"""
from {MCP_SERVER_NAME}.tool_2 import run, Params
result = run(Params(s="hello"))
print(result)
"""

        results = []
        async for item in code_executor.execute(code):
            match item:
                case ApprovalRequest():
                    await item.accept()
                case CodeExecutionResult():
                    results.append(item)

        assert len(results) == 1
        assert results[0].text is not None
        assert "You passed to tool 2: hello" in results[0].text

    @pytest.mark.asyncio
    async def test_tool_call_with_approval_rejected(self, code_executor: CodeExecutor):
        """Test calling a tool and rejecting the approval request."""
        code = f"""
from {MCP_SERVER_NAME}.tool_2 import run, Params
result = run(Params(s="hello"))
print(result)
"""

        with pytest.raises(CodeExecutionError) as exc_info:
            async for item in code_executor.execute(code):
                match item:
                    case ApprovalRequest():
                        await item.reject()

        assert "rejected" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_tool_with_structured_output(self, code_executor: CodeExecutor):
        """Test calling a tool with structured output (Pydantic model)."""
        code = f"""
from {MCP_SERVER_NAME}.tool_3 import run, Params
result = run(Params(name="test", level=2))
print(f"status={{result.status}}")
print(f"count={{result.count}}")
print(f"inner_code={{result.inner.code}}")
"""

        results = []
        async for item in code_executor.execute(code):
            match item:
                case ApprovalRequest():
                    await item.accept()
                case CodeExecutionResult():
                    results.append(item)

        assert len(results) == 1
        assert results[0].text is not None
        assert "status=completed_test" in results[0].text
        assert "count=4" in results[0].text
        assert "inner_code=200" in results[0].text

    @pytest.mark.asyncio
    async def test_multiple_tool_calls_in_sequence(self, code_executor: CodeExecutor):
        """Test multiple tool calls in one code block, handling each approval."""
        code = f"""
from {MCP_SERVER_NAME}.tool_1 import run as run_1, Params as Params1
from {MCP_SERVER_NAME}.tool_2 import run as run_2, Params as Params2

r1 = run_1(Params1(s="first"))
print(f"result1: {{r1}}")

r2 = run_2(Params2(s="second"))
print(f"result2: {{r2}}")
"""

        approvals = []
        results = []
        async for item in code_executor.execute(code):
            match item:
                case ApprovalRequest():
                    approvals.append(item)
                    await item.accept()
                case CodeExecutionResult():
                    results.append(item)

        assert len(approvals) == 2
        assert len(results) == 1
        assert results[0].text is not None
        assert "result1: You passed to tool 1: first" in results[0].text
        assert "result2: You passed to tool 2: second" in results[0].text

    @pytest.mark.asyncio
    async def test_tool_call_with_streaming(self, code_executor: CodeExecutor):
        """Test combining streaming output with tool approval."""
        code = f"""
from {MCP_SERVER_NAME}.tool_2 import run, Params

print("before tool call", flush=True)
result = run(Params(s="test"))
print(f"after tool call: {{result}}", flush=True)
"""

        chunks = []
        approvals = []
        result = None
        async for item in code_executor.execute(code, stream=True):
            match item:
                case CodeExecutionChunk():
                    chunks.append(item)
                case ApprovalRequest():
                    approvals.append(item)
                    await item.accept()
                case CodeExecutionResult():
                    result = item

        assert len(approvals) == 1
        combined_text = "".join(c.text for c in chunks)
        assert "before tool call" in combined_text
        assert "after tool call" in combined_text
        assert result is not None


class TestApprovalFlow:
    """Detailed approval behavior tests."""

    @pytest.mark.asyncio
    async def test_approval_request_contains_tool_info(self, code_executor: CodeExecutor):
        """Test that approval request contains server_name, tool_name, and tool_args."""
        code = f"""
from {MCP_SERVER_NAME}.tool_2 import run, Params
result = run(Params(s="hello"))
"""

        approval = None
        async for item in code_executor.execute(code):
            match item:
                case ApprovalRequest():
                    approval = item
                    await item.accept()

        assert approval is not None
        assert approval.server_name == MCP_SERVER_NAME
        assert approval.tool_name == "tool_2"
        assert approval.tool_args == {"s": "hello"}

    @pytest.mark.asyncio
    async def test_hyphenated_tool_name_preserved(self, code_executor: CodeExecutor):
        """Test that hyphenated tool names are preserved in approval request."""
        code = f"""
from {MCP_SERVER_NAME}.tool_1 import run, Params
result = run(Params(s="test"))
"""

        approval = None
        async for item in code_executor.execute(code):
            match item:
                case ApprovalRequest():
                    approval = item
                    await item.accept()

        assert approval is not None
        # tool-1 is the original MCP name, tool_1 is the sanitized module name
        assert approval.tool_name == "tool-1"


class TestExecutorLifecycle:
    """Tests for executor lifecycle management."""

    @pytest.mark.asyncio
    async def test_reset_clears_kernel_state(self, code_executor: CodeExecutor):
        """Test that reset() clears kernel state but allows continued execution."""
        # Set a variable
        async for _ in code_executor.execute("x = 42"):
            pass

        # Verify it exists
        result = None
        async for item in code_executor.execute("print(x)"):
            if isinstance(item, CodeExecutionResult):
                result = item
        assert result is not None
        assert result.text == "42"

        # Reset the executor
        await code_executor.reset()

        # Verify the variable no longer exists
        with pytest.raises(CodeExecutionError) as exc_info:
            async for _ in code_executor.execute("print(x)"):
                pass
        assert "NameError" in str(exc_info.value)

        # Verify we can still execute code
        result = None
        async for item in code_executor.execute("print('after reset')"):
            if isinstance(item, CodeExecutionResult):
                result = item
        assert result is not None
        assert result.text == "after reset"


@pytest.mark.skipif(sys.platform != "darwin", reason="Sandbox tests only run on macOS")
class TestSandbox:
    """Tests for sandbox configuration."""

    HTTP_CODE = """
import urllib.request
response = urllib.request.urlopen('https://httpbin.org/get')
content = response.read().decode('utf-8')
print(content)
"""

    @pytest.mark.asyncio
    async def test_custom_sandbox_allows_httpbin(self):
        """Test that custom sandbox config allows httpbin.org access."""
        async with CodeExecutor(
            sandbox=True,
            sandbox_config=Path("tests/integration/sandbox.json"),
            log_level="WARNING",
        ) as executor:
            result = None
            async for item in executor.execute(self.HTTP_CODE):
                if isinstance(item, CodeExecutionResult):
                    result = item

            assert result is not None
            assert result.text is not None
            data = json.loads(result.text)
            assert data["url"] == "https://httpbin.org/get"
            assert data["headers"]["Host"] == "httpbin.org"
