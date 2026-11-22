"""Design files: the browser fetches models from the backend, which proxies the CAD worker
(the worker's address is internal to the deployment)."""

from typing import Annotated, Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Path, Response

from app.api.jobs import get_runtime
from app.orchestrator.runtime import Runtime

router = APIRouter(prefix="/api/designs")

MEDIA_TYPES = {"glb": "model/gltf-binary", "step": "application/step"}


@router.get("/{design_id}/{kind}")
async def design_file(
    design_id: Annotated[str, Path(pattern=r"^[A-Za-z0-9_-]{1,64}$")],
    kind: Literal["glb", "step"],
    runtime: Annotated[Runtime, Depends(get_runtime)],
) -> Response:
    try:
        upstream = await runtime.cad.file(design_id, kind)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="CAD worker unreachable") from exc
    if upstream.status_code == 404:
        raise HTTPException(status_code=404, detail=f"design {design_id} not built")
    if upstream.status_code != 200:
        raise HTTPException(status_code=502, detail=f"CAD worker returned {upstream.status_code}")
    headers = {}
    if kind == "step":
        headers["Content-Disposition"] = f'attachment; filename="{design_id}.step"'
    return Response(content=upstream.content, media_type=MEDIA_TYPES[kind], headers=headers)
