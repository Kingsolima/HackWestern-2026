"""Shared board (docs/design/07 section 3). In memory now; the Tiger Data version implements the
same Protocol. BoardEntry itself rejects facts not written by the verifier, like the DB CHECK."""

from typing import Protocol

from app.schemas import BoardEntry, BoardKind


class Board(Protocol):
    async def post(self, entry: BoardEntry) -> None: ...

    async def read(
        self, job_id: str, kind: BoardKind | None = None, subject: str | None = None
    ) -> list[BoardEntry]: ...


class MemoryBoard:
    def __init__(self) -> None:
        self._rows: list[BoardEntry] = []

    async def post(self, entry: BoardEntry) -> None:
        self._rows.append(entry)

    async def read(
        self, job_id: str, kind: BoardKind | None = None, subject: str | None = None
    ) -> list[BoardEntry]:
        """Newest first."""
        return [
            row
            for row in reversed(self._rows)
            if row.job_id == job_id
            and (kind is None or row.kind == kind)
            and (subject is None or row.subject == subject)
        ]
