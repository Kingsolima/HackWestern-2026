"""Client for the CAD worker (cad/cad_worker/server.py). The backend only talks to CAD over HTTP."""

from typing import Any

import httpx


class CadError(RuntimeError):
    pass


class CadClient:
    def __init__(self, base_url: str, http: httpx.AsyncClient) -> None:
        self.base_url = base_url.rstrip("/")
        self.http = http

    async def build(self, design_id: str, **params: Any) -> dict[str, Any]:
        """POST /build. Returns {design_id, glb_url, step_url, fit}; the urls are CAD-worker
        paths such as /designs/{id}/glb."""
        try:
            resp = await self.http.post(
                f"{self.base_url}/build", json={"design_id": design_id, **params}, timeout=120.0
            )
        except httpx.HTTPError as exc:
            raise CadError(f"CAD worker unreachable at {self.base_url}: {exc}") from exc
        if resp.status_code != 200:
            raise CadError(
                f"CAD build {design_id} failed: HTTP {resp.status_code} {resp.text[:200]}"
            )
        return resp.json()
