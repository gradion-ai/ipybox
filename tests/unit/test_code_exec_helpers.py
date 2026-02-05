import asyncio
import time

import pytest

from ipybox.code_exec import _NoTimeoutBudget, _StreamWorker, _TimedBudget


@pytest.mark.asyncio
async def test_execution_budget_pause_excludes_time():
    queue: asyncio.Queue = asyncio.Queue()
    budget = _TimedBudget(0.2, queue)
    budget.pause()

    async def resume_and_put():
        await asyncio.sleep(0.3)
        budget.signal_resume(time.monotonic())
        await asyncio.sleep(0.05)
        await queue.put("ok")

    task = asyncio.create_task(resume_and_put())
    item = await asyncio.wait_for(budget.next_item(), timeout=1.0)
    assert item == "ok"
    await task


@pytest.mark.asyncio
async def test_budget_resume_before_queue_task_exists():
    queue: asyncio.Queue = asyncio.Queue()
    budget = _TimedBudget(0.5, queue)
    budget.pause()
    budget.signal_resume(time.monotonic())
    await queue.put("ready")

    item = await asyncio.wait_for(budget.next_item(), timeout=1.0)
    assert item == "ready"


@pytest.mark.asyncio
async def test_budget_resume_with_completed_queue_task():
    queue: asyncio.Queue = asyncio.Queue()
    budget = _TimedBudget(0.5, queue)
    budget.pause()
    await queue.put("queued")

    item = await asyncio.wait_for(budget.next_item(), timeout=1.0)
    assert item == "queued"


@pytest.mark.asyncio
async def test_budget_double_resume_is_idempotent():
    queue: asyncio.Queue = asyncio.Queue()
    budget = _TimedBudget(0.3, queue)
    budget.pause()
    budget.signal_resume(time.monotonic())
    budget.signal_resume(time.monotonic())
    await queue.put("ok")

    item = await asyncio.wait_for(budget.next_item(), timeout=1.0)
    assert item == "ok"


@pytest.mark.asyncio
async def test_budget_pause_is_idempotent():
    queue: asyncio.Queue = asyncio.Queue()
    budget = _TimedBudget(0.3, queue)
    budget.pause()
    budget.pause()
    budget.signal_resume(time.monotonic())
    await queue.put("ok")

    item = await asyncio.wait_for(budget.next_item(), timeout=1.0)
    assert item == "ok"


@pytest.mark.asyncio
async def test_no_timeout_budget_passthrough():
    queue: asyncio.Queue = asyncio.Queue()
    budget = _NoTimeoutBudget(queue)
    budget.pause()
    budget.on_decision()
    await queue.put("ok")

    item = await asyncio.wait_for(budget.next_item(), timeout=1.0)
    assert item == "ok"


@pytest.mark.asyncio
async def test_execution_budget_timeout_message():
    queue: asyncio.Queue = asyncio.Queue()
    budget = _TimedBudget(0.05, queue)

    with pytest.raises(asyncio.TimeoutError) as exc_info:
        await budget.next_item()

    assert "0.05s" in str(exc_info.value)


@pytest.mark.asyncio
async def test_stream_worker_enqueues_exception():
    async def stream():
        yield "first"
        raise ValueError("boom")

    worker = _StreamWorker(stream)
    await worker.start()

    item = await asyncio.wait_for(worker.queue.get(), timeout=1.0)
    error = await asyncio.wait_for(worker.queue.get(), timeout=1.0)

    assert item == "first"
    assert isinstance(error, ValueError)
    assert "boom" in str(error)

    await worker.finalize()
