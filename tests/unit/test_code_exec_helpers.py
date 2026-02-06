import asyncio

import pytest

from ipybox.code_exec import _NoTimeoutBudget, _StreamWorker, _TimedBudget


@pytest.mark.asyncio
async def test_execution_budget_pause_excludes_time():
    queue: asyncio.Queue = asyncio.Queue()
    budget = _TimedBudget(0.2, queue)
    budget.pause()

    async def resume_and_put():
        await asyncio.sleep(0.3)
        budget.on_decision(True)
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
    budget.on_decision(True)
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
async def test_budget_resume_while_queue_task_pending():
    queue: asyncio.Queue = asyncio.Queue()
    budget = _TimedBudget(0.5, queue)
    budget.pause()

    next_task = asyncio.create_task(budget.next_item())
    await asyncio.sleep(0.05)

    budget.on_decision(True)
    await asyncio.sleep(0.05)
    await queue.put("later")

    item = await asyncio.wait_for(next_task, timeout=1.0)
    assert item == "later"


@pytest.mark.asyncio
async def test_budget_double_resume_is_idempotent():
    queue: asyncio.Queue = asyncio.Queue()
    budget = _TimedBudget(0.3, queue)
    budget.pause()
    budget.on_decision(True)
    budget.on_decision(True)
    await queue.put("ok")

    item = await asyncio.wait_for(budget.next_item(), timeout=1.0)
    assert item == "ok"


@pytest.mark.asyncio
async def test_budget_pause_is_idempotent():
    queue: asyncio.Queue = asyncio.Queue()
    budget = _TimedBudget(0.3, queue)
    budget.pause()
    budget.pause()
    budget.on_decision(True)
    await queue.put("ok")

    item = await asyncio.wait_for(budget.next_item(), timeout=1.0)
    assert item == "ok"


@pytest.mark.asyncio
async def test_no_timeout_budget_passthrough():
    queue: asyncio.Queue = asyncio.Queue()
    budget = _NoTimeoutBudget(queue)
    budget.pause()
    budget.on_decision(True)
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
async def test_budget_paused_wait_cleans_up_on_cancel():
    queue: asyncio.Queue = asyncio.Queue()
    budget = _TimedBudget(0.5, queue)
    budget.pause()

    task = asyncio.create_task(budget.next_item())
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    budget.on_decision(True)
    await queue.put("ok")
    item = await asyncio.wait_for(budget.next_item(), timeout=1.0)
    assert item == "ok"


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
