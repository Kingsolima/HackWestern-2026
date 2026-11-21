import asyncio

import pytest

from app.orchestrator.events import EventLog, RunProgress, StagePayload

pytestmark = pytest.mark.anyio


async def test_emit_numbers_events_and_sets_type_from_payload():
    log = EventLog("j1")
    first = await log.emit(StagePayload(stage="PLAN"))
    second = await log.emit(RunProgress(run_id="r", purpose="p"))
    assert (first.id, first.type, first.data) == (1, "stage", {"stage": "PLAN"})
    assert (second.id, second.type, second.job_id) == (2, "run_progress", "j1")


async def test_subscribe_replays_after_id_then_follows_until_close():
    log = EventLog("j1")
    for stage in ("PLAN", "DISCOVER"):
        await log.emit(StagePayload(stage=stage))

    async def produce():
        await asyncio.sleep(0.01)
        await log.emit(StagePayload(stage="TRIAGE"))
        await log.close()

    task = asyncio.create_task(produce())
    got = [e.data["stage"] async for e in log.subscribe(after_id=1)]
    await task
    assert got == ["DISCOVER", "TRIAGE"]


async def test_subscribe_to_closed_log_returns_history():
    log = EventLog("j1")
    await log.emit(StagePayload(stage="DONE"))
    await log.close()
    assert [e.id async for e in log.subscribe()] == [1]


async def test_closed_log_rejects_new_events():
    log = EventLog("j1")
    await log.close()
    with pytest.raises(RuntimeError):
        await log.emit(StagePayload(stage="DONE"))
