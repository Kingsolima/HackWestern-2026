"""Tiger Data (Postgres + TimescaleDB) connection helper. Schema lives in db/schema.sql."""

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool
from pydantic import BaseModel

from app.config import REPO_ROOT, settings
from app.schemas import BoardEntry, BoardKind

SCHEMA = REPO_ROOT / "db" / "schema.sql"


@asynccontextmanager
async def connect() -> AsyncIterator[psycopg.AsyncConnection]:
    async with await psycopg.AsyncConnection.connect(settings.database_url) as conn:
        yield conn


class RunRow(BaseModel):
    """One agent_runs row: a finished TinyFish or Gemini call."""

    time: datetime
    job_id: str
    run_id: str
    worker: str
    product: str
    site: str
    status: str  # the run's outcome
    reason: str
    duration_s: float
    live: bool


class SiteSuccess(BaseModel):
    site: str
    runs: int
    successes: int


class TigerDB:
    """One pool per process. Every method is a single short statement in autocommit."""

    def __init__(self, url: str, max_size: int = 4) -> None:
        self.pool = AsyncConnectionPool(
            url, min_size=1, max_size=max_size, open=False, kwargs={"autocommit": True}
        )

    async def open(self) -> None:
        await self.pool.open(wait=True, timeout=20)

    async def close(self) -> None:
        await self.pool.close()

    async def apply_schema(self, path: Path = SCHEMA) -> None:
        """Idempotent (IF NOT EXISTS everywhere). Continuous aggregates cannot be created in a
        transaction, so the file runs statement by statement in autocommit."""
        statements = [s.strip() for s in _strip_comments(path.read_text()).split(";")]
        async with self.pool.connection() as conn:
            for stmt in statements:
                if stmt:
                    await conn.execute(stmt)

    async def insert_run(self, row: RunRow) -> None:
        async with self.pool.connection() as conn:
            await conn.execute(
                "INSERT INTO agent_runs (time, job_id, run_id, worker, product, site, status,"
                " reason, duration_s, live) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    row.time,
                    row.job_id,
                    row.run_id,
                    row.worker,
                    row.product,
                    row.site,
                    row.status,
                    row.reason[:500],
                    row.duration_s,
                    row.live,
                ),
            )

    async def insert_board(self, e: BoardEntry) -> None:
        async with self.pool.connection() as conn:
            await conn.execute(
                "INSERT INTO board (time, job_id, author, bom_line, kind, subject, payload,"
                " claim_id, verified) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    e.time,
                    e.job_id,
                    e.author,
                    e.bom_line,
                    e.kind,
                    e.subject,
                    json.dumps(e.payload, default=str),
                    e.claim_id,
                    e.verified,
                ),
            )

    async def read_board(
        self, job_id: str, kind: BoardKind | None, subject: str | None
    ) -> list[BoardEntry]:
        async with self.pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "SELECT time, job_id, author, bom_line, kind, subject, payload, claim_id, verified"
                " FROM board WHERE job_id = %s AND (%s::text IS NULL OR kind = %s)"
                " AND (%s::text IS NULL OR subject = %s) ORDER BY time DESC",
                (job_id, kind, kind, subject, subject),
            )
            return [BoardEntry.model_validate(r) for r in await cur.fetchall()]

    async def site_success(self, hours: int = 24) -> list[SiteSuccess]:
        """From the continuous aggregate (real-time on, so the newest runs count too)."""
        async with self.pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "SELECT site, sum(runs)::int AS runs, sum(successes)::int AS successes"
                " FROM site_success_hourly WHERE bucket > now() - make_interval(hours => %s)"
                " GROUP BY site ORDER BY runs DESC, site",
                (hours,),
            )
            return [SiteSuccess.model_validate(r) for r in await cur.fetchall()]


def _strip_comments(sql: str) -> str:
    return "\n".join(line.split("--", 1)[0] for line in sql.splitlines())
