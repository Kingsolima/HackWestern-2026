"""Client for Omar's CAD worker (cad/cad_worker/server.py): POST /build -> model URLs + the fit
numbers the checks need. The worker owns all bracket geometry; the backend sends only motor
and wheel facts. Not recorded: the worker is our own deterministic service."""

from typing import Any

import httpx
from pydantic import BaseModel

from app.schemas import NemaFrameName

BUILDABLE_FRAMES: frozenset[str] = frozenset({"17", "23", "34"})
# Fit numbers the 05 checks read (engineering/spec_checks.py _fit). A build without them is a
# contract break with the worker, reported like an outage.
FIT_KEYS: frozenset[str] = frozenset(
    {
        "fit_envelope",
        "envelope_used_mm",
        "inboard_room_mm",
        "ground_clearance_mm",
        "fit_ground",
        "wheel_bore_mm",
        "needs_hub_adapter",
    }
)


class CadError(RuntimeError):
    """The CAD worker is unreachable or refused the build."""


class CadBuild(BaseModel):
    design_id: str
    glb_url: str
    step_url: str
    fit: dict[str, Any]


class CadClient:
    def __init__(self, http: httpx.AsyncClient, base_url: str) -> None:
        self._http = http
        self.base_url = base_url.rstrip("/")

    async def build(
        self,
        design_id: str,
        frame: NemaFrameName | None,
        wheel_r_mm: float,
        body_len_mm: float | None = None,
        shaft_d_mm: float | None = None,
        highlight: bool = False,
        robot: str = "wheeled",
    ) -> CadBuild | None:
        """None when the frame cannot be modelled; CadError when the worker is unreachable or
        refuses. Either way the fit checks go to Review instead of failing the job. highlight
        colours the regenerated bracket in the viewer."""
        if frame not in BUILDABLE_FRAMES:
            return None
        body: dict[str, Any] = {
            "design_id": design_id,
            "frame": frame,
            "wheel_r": wheel_r_mm,
            "highlight": highlight,
        }
        if robot != "wheeled":
            body["robot"] = robot
        if body_len_mm is not None:
            body["body_len"] = body_len_mm
        if shaft_d_mm is not None:
            body["shaft_d"] = shaft_d_mm
        if not self.base_url:
            raise CadError("no CAD worker configured (CAD_WORKER_URL)")
        try:
            r = await self._http.post(f"{self.base_url}/build", json=body, timeout=120.0)
        except httpx.HTTPError as exc:
            raise CadError(f"CAD worker unreachable at {self.base_url}: {exc}") from exc
        if r.status_code != 200:
            raise CadError(f"CAD build {design_id} failed: HTTP {r.status_code} {r.text[:200]}")
        built = CadBuild.model_validate(r.json())
        if robot != "wheeled":
            return built  # generic fit_checks rows; a missing list reads as review
        missing = FIT_KEYS - built.fit.keys()
        if missing or "min_ground_clearance" not in built.fit.get("params", {}):
            gaps = sorted(missing) or ["params.min_ground_clearance"]
            raise CadError(f"CAD build {design_id} returned no {', '.join(gaps)}")
        return built

    async def file(self, design_id: str, kind: str) -> httpx.Response:
        return await self._http.get(f"{self.base_url}/designs/{design_id}/{kind}", timeout=60.0)
