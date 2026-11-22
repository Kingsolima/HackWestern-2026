"""Record/replay boundary for every external call (docs/design/04 section 6).

A request is keyed by sha256 of its product and canonical JSON; the API key never enters the
request dict, so recordings hold no secrets. Recordings are gzip JSON under
`<root>/<product>/<key>.json.gz` and are committed so a demo job replays offline.
"""

import asyncio
import gzip
import hashlib
import json
import os
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.schemas import JobMode, Product


class ReplayMiss(LookupError):
    """Replay mode asked for a call that was never recorded."""


def request_key(product: Product, request: dict[str, Any]) -> str:
    canonical = json.dumps(
        {"product": product, "request": request}, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


class Recorder:
    def __init__(self, root: Path, mode: JobMode, replay_speed: float = 1.0) -> None:
        """replay_speed scales recorded stream pacing: 1.0 = as recorded, 0 = no waits."""
        self.root = root
        self.mode = mode
        self.replay_speed = replay_speed

    def path(self, product: Product, request: dict[str, Any]) -> Path:
        return self.root / product / f"{request_key(product, request)}.json.gz"

    def _load(self, product: Product, request: dict[str, Any]) -> dict[str, Any] | None:
        if self.mode == "live":
            return None
        path = self.path(product, request)
        if path.exists():
            with gzip.open(path, "rt", encoding="utf-8") as f:
                return json.load(f)
        if self.mode == "replay":
            raise ReplayMiss(f"no recording for {product} {request_key(product, request)[:12]}")
        return None

    def recorded(self, product: Product, request: dict[str, Any]) -> dict[str, Any] | None:
        """The recorded response for a call, in any mode; None when it was never recorded."""
        path = self.path(product, request)
        if not path.exists():
            return None
        with gzip.open(path, "rt", encoding="utf-8") as f:
            return json.load(f).get("response")

    def _save(self, product: Product, request: dict[str, Any], body: dict[str, Any]) -> None:
        path = self.path(product, request)
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "product": product,
            "request": request,
            "recorded_at": datetime.now(UTC).isoformat(),
        } | body
        tmp = path.with_suffix(".tmp")
        with gzip.open(tmp, "wt", encoding="utf-8") as f:
            json.dump(record, f, sort_keys=True)
        os.replace(tmp, path)

    async def call(
        self,
        product: Product,
        request: dict[str, Any],
        live_fn: Callable[[], Awaitable[dict[str, Any]]],
    ) -> tuple[dict[str, Any], bool]:
        """Returns (response, live)."""
        recorded = self._load(product, request)
        if recorded is not None:
            return recorded["response"], False
        response = await live_fn()
        self._save(product, request, {"response": response})
        return response, True

    async def stream(
        self,
        product: Product,
        request: dict[str, Any],
        live_fn: Callable[[], AsyncIterator[dict[str, Any]]],
    ) -> AsyncIterator[tuple[dict[str, Any], bool]]:
        """Yields (event, live). A live stream is saved only once it ends cleanly."""
        recorded = self._load(product, request)
        if recorded is not None:
            for item in recorded["events"]:
                if self.replay_speed > 0:
                    await asyncio.sleep(item["dt"] * self.replay_speed)
                yield item["event"], False
            return
        events: list[dict[str, Any]] = []
        last = time.monotonic()
        async for event in live_fn():
            now = time.monotonic()
            events.append({"dt": round(now - last, 3), "event": event})
            last = now
            yield event, True
        self._save(product, request, {"events": events})
