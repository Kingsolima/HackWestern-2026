"""Part workers: code loops, one per BOM line (docs/design/07 section 2).

Only the fake swap worker exists so far; it drives the pipeline and the UI end to end against a
committed recording of a made-up page (data/recordings/fetch, `fake: true`).
"""

from datetime import UTC, datetime
from typing import Protocol

from app.orchestrator.context import JobContext
from app.orchestrator.events import RunFinished, RunProgress, RunStarted
from app.schemas import Claim, Source


class Worker(Protocol):
    name: str

    async def run(self, ctx: JobContext) -> list[Claim]:
        """Dispatch runs, emit run_* events, return raw (unverified) claims."""
        ...


FAKE_URL = "https://example.invalid/fake-motor"
FAKE_HTML = (
    "<html><body><h1>FAKE-23 test motor (not a real product)</h1>"
    "<p>Continuous torque: <b>0.50</b> N-m</p>"
    "<p>Rated speed: 3,000&nbsp;rpm</p>"
    "<p>Regular price $299</p><p>Sale price $265</p>"
    "<p>Made in USA at our Ohio plant.</p></body></html>"
)
_FAKE_CLAIMS = [
    ("continuous_torque", "0.50", "N-m", "Continuous torque: 0.50 N-m"),
    ("rated_speed", "3000", "rpm", "Rated speed: 3,000 rpm"),
    ("price", "265", "USD", "Regular price $299"),
    ("country_of_origin", "US", None, "Made in USA at our Ohio plant."),
]


class FakeSwapWorker:
    """Stands in for the swap worker until chunk 2; its run is labelled fake and not live."""

    name = "swap:drive_motor"

    async def run(self, ctx: JobContext) -> list[Claim]:
        run_id = f"fake-{ctx.job_id}"
        log = ctx.log
        await log.emit(
            RunStarted(
                run_id=run_id,
                worker=self.name,
                product="agent",
                site="example.invalid",
                url=FAKE_URL,
                goal="Fake run: read specs and origin of FAKE-23",
                live=False,
            )
        )
        await log.emit(RunProgress(run_id=run_id, purpose="Fake run: reading the spec table"))
        await log.emit(
            RunFinished(run_id=run_id, outcome="success", reason="fake", duration_s=0, live=False)
        )
        source = Source(url=FAKE_URL, kind="page", fetched_at=datetime.now(UTC), via="replay")
        return [
            Claim(
                id=f"{run_id}:{field}",
                candidate_id="fake-23",
                field=field,
                raw_value=value,
                raw_unit=unit,
                quote=quote,
                source=source,
                extracted_by="tinyagent",
            )
            for field, value, unit, quote in _FAKE_CLAIMS
        ]
