"""Writes one agent_runs row per finished run, from the job's own event log: run_started gives
the site, product and worker, run_finished the outcome. Stage code is untouched, and a replayed
job writes rows too (live=false), so the success-by-site panel shows what the demo shows."""

import logging
from typing import Protocol

import psycopg

from app.db.tiger import RunRow, SiteSuccess
from app.orchestrator.events import Event, EventLog

log = logging.getLogger(__name__)


class RunSink(Protocol):
    async def insert_run(self, row: RunRow) -> None: ...


def run_rows(events: list[Event]) -> list[RunRow]:
    """Pair each run_finished with its run_started; unpaired finishes are skipped."""
    started: dict[str, Event] = {}
    rows: list[RunRow] = []
    for e in events:
        if e.type == "run_started":
            started[e.data["run_id"]] = e
        elif e.type == "run_finished" and e.data["run_id"] in started:
            s = started[e.data["run_id"]].data
            rows.append(
                RunRow(
                    time=e.ts,
                    job_id=e.job_id,
                    run_id=e.data["run_id"],
                    worker=s["worker"],
                    product=s["product"],
                    site=s["site"],
                    status=e.data["outcome"],
                    reason=e.data["reason"],
                    duration_s=e.data["duration_s"],
                    live=e.data["live"],
                )
            )
    return rows


async def record_runs(log_: EventLog, sink: RunSink) -> int:
    """Follow the log until it closes, writing each finished run as it arrives. A database
    error is logged and that row skipped: the job never waits on or fails because of Tiger."""
    started: dict[str, Event] = {}
    written = 0
    async for event in log_.subscribe():
        if event.type == "run_started":
            started[event.data["run_id"]] = event
        elif event.type == "run_finished" and event.data["run_id"] in started:
            [row] = run_rows([started[event.data["run_id"]], event])
            try:
                await sink.insert_run(row)
                written += 1
            except psycopg.Error:  # pool timeouts are psycopg errors too
                log.exception("agent_runs insert failed for %s", row.run_id)
    return written


def site_success_from(logs: list[EventLog]) -> list[SiteSuccess]:
    """The same numbers from in-memory jobs, for runs without Tiger configured."""
    by_site: dict[str, list[int]] = {}
    for lg in logs:
        for row in run_rows(lg.events):
            runs = by_site.setdefault(row.site, [0, 0])
            runs[0] += 1
            runs[1] += row.status == "success"
    return sorted(
        (SiteSuccess(site=s, runs=n, successes=ok) for s, (n, ok) in by_site.items()),
        key=lambda x: (-x.runs, x.site),
    )
