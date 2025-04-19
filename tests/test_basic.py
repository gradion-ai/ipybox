import pytest

from ipybox import ExecutionClient, ExecutionContainer


@pytest.fixture(scope="module")
async def execution_client(workspace: str):
    async with ExecutionContainer(
        tag="ghcr.io/gradion-ai/ipybox:minimal",
        binds={workspace: "workspace"},
    ) as container:
        async with ExecutionClient(host="localhost", port=container.executor_port) as client:
            yield client


@pytest.mark.asyncio(loop_scope="module")
async def test_basic_functionality(execution_client):
    result = await execution_client.execute("print('Hello, world!')")
    assert result.text == "Hello, world!"
