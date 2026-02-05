import asyncio

import pytest

from ipybox.tool_exec.approval.client import ApprovalRequest


@pytest.mark.asyncio
async def test_response_resolves_before_send():
    finish = asyncio.Event()

    async def respond(value: bool):
        await finish.wait()

    request = ApprovalRequest(
        server_name="srv",
        tool_name="tool",
        tool_args={},
        respond=respond,
    )

    accept_task = asyncio.create_task(request.accept())
    response_task = asyncio.create_task(request.response())

    result = await asyncio.wait_for(response_task, timeout=0.5)
    assert result is True

    finish.set()
    await accept_task


@pytest.mark.asyncio
async def test_on_decision_callback_receives_value():
    finished = asyncio.Event()
    received: list[bool] = []

    async def respond(value: bool):
        finished.set()

    request = ApprovalRequest(
        server_name="srv",
        tool_name="tool",
        tool_args={},
        respond=respond,
    )

    request.on_decision(received.append)
    await request.reject()
    await asyncio.wait_for(finished.wait(), timeout=0.5)
    await asyncio.sleep(0)
    assert received == [False]
