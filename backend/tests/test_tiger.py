"""agent_runs recording, the success-by-site API, and (opt-in, TIGER_TEST=1) the real schema on
Tiger Cloud: board CHECK, hypertables and the real-time continuous aggregate."""

import os
import uuid

import psycopg
import pytest

from app.db.tiger import RunRow
from app.orchestrator.events import EventLog, RunFinished, RunStarted, StagePayload
from app.orchestrator.run_log import record_runs, run_rows, site_success_from
from app.schemas import BoardEntry

pytestmark = pytest.mark.anyio


async def job_log(job_id="j1"):
    log = EventLog(job_id)
    await log.emit(StagePayload(stage="DISCOVER"))
    for run_id, site, outcome in [
        ("r1", "teknic.com", "success"),
        ("r2", "scribd.com", "blocked"),
        ("r3", "teknic.com", "incomplete"),
    ]:
        await log.emit(
            RunStarted(
                run_id=run_id,
                worker="swap",
                product="agent",
                site=site,
                url=None,
                goal="g",
                live=False,
            )
        )
        await log.emit(
            RunFinished(run_id=run_id, outcome=outcome, reason="why", duration_s=1.5, live=False)
        )
    await log.emit(
        RunFinished(run_id="orphan", outcome="success", reason="", duration_s=0, live=False)
    )
    return log


async def test_run_rows_pair_started_and_finished_and_skip_orphans():
    rows = run_rows((await job_log()).events)
    assert [(r.run_id, r.site, r.status, r.worker, r.product) for r in rows] == [
        ("r1", "teknic.com", "success", "swap", "agent"),
        ("r2", "scribd.com", "blocked", "swap", "agent"),
        ("r3", "teknic.com", "incomplete", "swap", "agent"),
    ]
    assert rows[0].job_id == "j1" and rows[0].duration_s == 1.5 and rows[0].live is False


class FlakySink:
    def __init__(self):
        self.rows: list[RunRow] = []

    async def insert_run(self, row):
        if row.run_id == "r2":
            raise psycopg.OperationalError("connection lost")
        self.rows.append(row)


async def test_recorder_follows_the_log_and_survives_a_database_error():
    log = await job_log()
    await log.close()
    sink = FlakySink()
    assert await record_runs(log, sink) == 2
    assert [r.run_id for r in sink.rows] == ["r1", "r3"]


async def test_site_success_from_memory():
    sites = site_success_from([await job_log("a"), await job_log("b")])
    assert [(s.site, s.runs, s.successes) for s in sites] == [
        ("teknic.com", 4, 2),
        ("scribd.com", 2, 0),
    ]


def test_sites_api_uses_memory_without_tiger(client):
    from tests.test_jobs_api import NoClaimWorker, sse_events, start

    sse_events(client, start(client, NoClaimWorker()))
    r = client.get("/api/sites/success")
    assert r.status_code == 200 and r.json()["source"] == "memory"


# --- live, opt-in: TIGER_TEST=1 with DATABASE_URL pointing at a Tiger Cloud service ----------

live = pytest.mark.skipif(os.environ.get("TIGER_TEST") != "1", reason="set TIGER_TEST=1")


@pytest.fixture
async def tiger():
    from app.config import Settings
    from app.db.tiger import TigerDB

    db = TigerDB(Settings().database_url)
    await db.open()
    await db.apply_schema()
    job_id = f"test-{uuid.uuid4().hex[:8]}"
    yield db, job_id
    async with db.pool.connection() as conn:
        await conn.execute("DELETE FROM board WHERE job_id = %s", (job_id,))
        await conn.execute("DELETE FROM agent_runs WHERE job_id = %s", (job_id,))
    await db.close()


@live
async def test_schema_applies_twice(tiger):
    db, _ = tiger
    await db.apply_schema()  # idempotent


@live
async def test_board_round_trip_and_the_database_rejects_non_verifier_facts(tiger):
    from app.orchestrator.board import TigerBoard

    db, job_id = tiger
    board = TigerBoard(db)
    await board.post(
        BoardEntry(
            job_id=job_id,
            author="verifier",
            kind="fact",
            subject="Teknic",
            payload={"field": "price", "value": "452"},
            claim_id="c1",
            verified=True,
        )
    )
    await board.post(
        BoardEntry(
            job_id=job_id,
            author="swap",
            kind="hint",
            subject="Teknic",
            payload={"note": "try SDHP"},
        )
    )
    facts = await board.read(job_id, kind="fact")
    assert [(f.subject, f.payload["value"], f.claim_id) for f in facts] == [("Teknic", "452", "c1")]
    assert len(await board.read(job_id)) == 2
    async with db.pool.connection() as conn:
        with pytest.raises(psycopg.errors.CheckViolation):
            await conn.execute(
                "INSERT INTO board (job_id, author, kind, subject, payload, verified)"
                " VALUES (%s, 'swap', 'fact', 'x', '{}', true)",
                (job_id,),
            )


@live
async def test_runs_reach_the_real_time_aggregate_at_once(tiger):
    db, job_id = tiger
    log = await job_log(job_id)
    await log.close()
    assert await record_runs(log, db) == 3
    sites = {s.site: s for s in await db.site_success()}
    assert sites["teknic.com"].runs >= 2 and sites["scribd.com"].runs >= 1
