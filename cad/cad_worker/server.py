"""CAD worker HTTP API. One /build call per design; the orchestrator runs them in parallel.

    POST /build                {design_id, frame, body_len, shaft_d?, ...} -> urls + fit numbers
    GET  /designs/{id}/glb     model for the browser viewer
    GET  /designs/{id}/step    engineering export
    GET  /designs/{id}/fit     geometry numbers for the checks (05-checks-spec §4)

Part names in the GLB (bracket_left, motor_right, hub_adapter_left, ...) let the viewer
highlight what changed. TODO(owner 1): upload outputs to Vultr Object Storage.
"""

import json
import os
import re
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from cad_worker.export import export
from cad_worker.robot import RobotParams, measure, robot

OUT_DIR = Path(os.environ.get("CAD_OUT_DIR", "out"))
OUT_DIR.mkdir(parents=True, exist_ok=True)
DESIGN_ID = r"^[A-Za-z0-9_-]{1,64}$"

app = FastAPI(title="CAD worker")
app.mount("/files", StaticFiles(directory=OUT_DIR), name="files")


class BuildRequest(BaseModel):
    design_id: str = Field(pattern=DESIGN_ID)
    frame: Literal["17", "23", "34"] = "23"
    body_len: float = Field(56.0, gt=0, le=300)
    shaft_d: float | None = Field(None, gt=0, le=30)
    wheel_r: float = Field(60.0, gt=0)
    wheel_bore: float = Field(6.35, gt=0)
    min_ground_clearance: float = 10.0


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/build")
def build(req: BuildRequest) -> dict:
    params = RobotParams(**req.model_dump(exclude={"design_id"}))
    fit = measure(params)
    export(robot(params), OUT_DIR, req.design_id)
    (OUT_DIR / f"{req.design_id}.fit.json").write_text(json.dumps(fit, indent=2))
    base = f"/designs/{req.design_id}"
    return {
        "design_id": req.design_id,
        "glb_url": f"{base}/glb",
        "step_url": f"{base}/step",
        "fit": fit,
    }


def _design_file(design_id: str, suffix: str) -> Path:
    if not re.fullmatch(DESIGN_ID, design_id):
        raise HTTPException(400, "bad design id")
    path = OUT_DIR / f"{design_id}{suffix}"
    if not path.exists():
        raise HTTPException(404, f"design {design_id} not built")
    return path


@app.get("/designs/{design_id}/glb")
def get_glb(design_id: str) -> FileResponse:
    return FileResponse(_design_file(design_id, ".glb"), media_type="model/gltf-binary")


@app.get("/designs/{design_id}/step")
def get_step(design_id: str) -> FileResponse:
    path = _design_file(design_id, ".step")
    return FileResponse(path, media_type="application/step", filename=path.name)


@app.get("/designs/{design_id}/fit")
def get_fit(design_id: str) -> dict:
    return json.loads(_design_file(design_id, ".fit.json").read_text())
