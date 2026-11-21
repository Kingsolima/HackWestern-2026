"""CAD worker HTTP API. One /build call per tournament design; the orchestrator runs them in
parallel. TODO(owner 1): upload outputs to Vultr Object Storage and return URLs."""

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from cad_worker.export import export
from cad_worker.robot import RobotParams, robot

OUT_DIR = Path(os.environ.get("CAD_OUT_DIR", "out"))
OUT_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="CAD worker")
app.mount("/files", StaticFiles(directory=OUT_DIR), name="files")


class BuildRequest(BaseModel):
    design_id: str
    frame: str = "23"
    body_len: float = 56.0
    clearance: float = 5.0


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/build")
def build(req: BuildRequest) -> dict[str, str]:
    params = RobotParams(frame=req.frame, body_len=req.body_len, clearance=req.clearance)
    paths = export(robot(params), OUT_DIR, req.design_id)
    return {k: f"/files/{p.name}" for k, p in paths.items()}
