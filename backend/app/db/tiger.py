"""Tiger Data (Postgres + TimescaleDB) connection helper. Schema lives in db/schema.sql."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import psycopg

from app.config import settings


@asynccontextmanager
async def connect() -> AsyncIterator[psycopg.AsyncConnection]:
    async with await psycopg.AsyncConnection.connect(settings.database_url) as conn:
        yield conn
