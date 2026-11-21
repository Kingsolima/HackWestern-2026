"""Fixture store for record/replay (docs/design/04-architecture.md §6).

A fixture is keyed by the product and the request body only. Headers (and so the API key)
are never part of the key or the stored file, so fixtures are safe to commit.
"""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import settings


class FixtureMissing(LookupError):
    """Replay was asked for a request that was never recorded."""


def fixture_key(product: str, request: dict[str, Any]) -> str:
    canonical = json.dumps({"product": product, "request": request}, sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


class Recorder:
    def __init__(self, root: Path | None = None):
        self.root = (root or settings.fixtures_dir) / "tinyfish"

    def path(self, product: str, request: dict[str, Any]) -> Path:
        return self.root / f"{product}-{fixture_key(product, request)[:16]}.json"

    def save(self, product: str, request: dict[str, Any], payload: dict[str, Any]) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        p = self.path(product, request)
        record = {
            "product": product,
            "request": request,
            "recorded_at": datetime.now(UTC).isoformat(),
            **payload,
        }
        p.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n")
        return p

    def load(self, product: str, request: dict[str, Any]) -> dict[str, Any]:
        p = self.path(product, request)
        if not p.exists():
            raise FixtureMissing(f"no {product} fixture at {p.name}; run once with mode=live")
        return json.loads(p.read_text())
