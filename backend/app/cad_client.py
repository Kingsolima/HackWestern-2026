"""Client for Omar's CAD worker (cad/cad_worker/server.py): POST /build -> model URLs + the fit
numbers the checks need. The worker owns all bracket geometry; the backend sends only motor
and wheel facts. Not recorded: the worker is our own deterministic service."""

from typing import Any

import httpx
from pydantic import BaseModel

from app.schemas import NemaFrameName

BUILDABLE_FRAMES: frozenset[str] = frozenset({"17", "23", "34"})


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
    ) -> CadBuild | None:
        """None when the frame cannot be modelled or the worker is unreachable; the fit checks
        then go to Review instead of failing the job."""
        if frame not in BUILDABLE_FRAMES:
            return None
        body: dict[str, Any] = {"design_id": design_id, "frame": frame, "wheel_r": wheel_r_mm}
        if body_len_mm is not None:
            body["body_len"] = body_len_mm
        if shaft_d_mm is not None:
            body["shaft_d"] = shaft_d_mm
        try:
            r = await self._http.post(f"{self.base_url}/build", json=body, timeout=60.0)
            r.raise_for_status()
        except httpx.HTTPError:
            return None
        return CadBuild.model_validate(r.json())

    async def file(self, design_id: str, kind: str) -> httpx.Response:
        return await self._http.get(f"{self.base_url}/designs/{design_id}/{kind}", timeout=60.0)
