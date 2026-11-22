"""CAD worker HTTP API. One /build call per design; the orchestrator runs them in parallel.

    POST /build                {design_id, robot?, frame, body_len, shaft_d?, ...} -> urls + fit
    GET  /designs/{id}/glb     model for the browser viewer
    GET  /designs/{id}/step    engineering export
    GET  /designs/{id}/fit     geometry numbers for the checks (05-checks-spec §4)
    POST /measure              STEP bytes -> parts with bounding boxes and volumes (onboarding)

robot is "wheeled" (default, the v3 demo robot), "ar4" (the arm's J2 drive, BUILD-PLAN-v4 §7) or
"stretch" (a block-level mobile manipulator with a NEMA 34 shoulder drive).
Every fit has generic `fit_checks` rows {name, value, limit, unit, ok} for the backend.

Starter designs are built at startup, so the page has a robot to show before any job has run:
"starter" (wheeled, NEMA 23 stepper baseline), "starter_ar4" (AR4 arm, NEMA 23 J2 motor) and
"starter_stretch" (Stretch, NEMA 34 shoulder motor).

Part names in the GLB (bracket_left, motor_right, hub_adapter_left, ...) let the viewer
highlight what changed. TODO(owner 1): upload outputs to Vultr Object Storage.
"""

import json
import os
import re
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from cad_worker.arm import ArmParams, arm, arm_meshes, measure_arm
from cad_worker.export import export
from cad_worker.measure import measure_step
from cad_worker.robot import RobotParams, measure, robot
from cad_worker.stretch import StretchParams, measure_stretch, stretch

OUT_DIR = Path(os.environ.get("CAD_OUT_DIR", "out"))
OUT_DIR.mkdir(parents=True, exist_ok=True)
DESIGN_ID = r"^[A-Za-z0-9_-]{1,64}$"

Params = RobotParams | ArmParams | StretchParams

STARTERS: dict[str, Params] = {
    # Same robot as the orchestrator's BUILD baseline (backend/app/orchestrator/job.py): NEMA 23
    # stepper, default body length, 6.35 mm shaft and wheel bore, 60 mm wheels.
    "starter": RobotParams(),
    "starter_ar4": ArmParams(),
    "starter_stretch": StretchParams(),
}


def build_design(design_id: str, params: Params) -> dict:
    meshes = None
    if isinstance(params, ArmParams):
        fit, assy, meshes = measure_arm(params), arm(params), arm_meshes()
    elif isinstance(params, StretchParams):
        fit, assy = measure_stretch(params), stretch(params)
    else:
        fit, assy = measure(params), robot(params)
    export(assy, OUT_DIR, design_id, extra_meshes=meshes)
    (OUT_DIR / f"{design_id}.fit.json").write_text(json.dumps(fit, indent=2))
    base = f"/designs/{design_id}"
    return {
        "design_id": design_id,
        "glb_url": f"{base}/glb",
        "step_url": f"{base}/step",
        "fit": fit,
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Rebuilt every start so they always match the current CAD code.
    for design_id, params in STARTERS.items():
        build_design(design_id, params)
    yield


app = FastAPI(title="CAD worker", lifespan=lifespan)
app.mount("/files", StaticFiles(directory=OUT_DIR), name="files")


class BuildRequest(BaseModel):
    design_id: str = Field(pattern=DESIGN_ID)
    robot: Literal["wheeled", "ar4", "stretch"] = "wheeled"
    frame: Literal["17", "23", "34"] = "23"
    # None = the robot model's own baseline motor length (56 mm; 120 mm on stretch)
    body_len: float | None = Field(None, gt=0, le=300)
    shaft_d: float | None = Field(None, gt=0, le=30)
    pilot_d: float | None = Field(None, gt=0, le=120)
    bolt_spacing: float | None = Field(None, gt=0, le=120)
    highlight: bool = False
    # wheeled only
    wheel_r: float = Field(60.0, gt=0)
    wheel_bore: float = Field(6.35, gt=0)
    min_ground_clearance: float = 10.0
    # ar4 only (stretch uses its own gearbox bore and shoulder space)
    gearbox_bore: float = Field(6.35, gt=0, le=30)
    j2_space: float = Field(190.0, gt=0, le=500)

    def params(self) -> Params:
        common = self.model_dump(
            include={"frame", "body_len", "shaft_d", "pilot_d", "bolt_spacing", "highlight"},
            exclude_none=True,
        )
        if self.robot == "ar4":
            return ArmParams(**common, gearbox_bore=self.gearbox_bore, j2_space=self.j2_space)
        if self.robot == "stretch":
            return StretchParams(**common)
        return RobotParams(
            **common,
            wheel_r=self.wheel_r,
            wheel_bore=self.wheel_bore,
            min_ground_clearance=self.min_ground_clearance,
        )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/build")
def build(req: BuildRequest) -> dict:
    return build_design(req.design_id, req.params())


MAX_STEP_BYTES = 25 * 1024 * 1024


@app.post("/measure")
async def measure_upload(request: Request) -> dict:
    """The request body is the STEP file itself. Nothing is kept: the file is measured from a
    temporary copy."""
    data = await request.body()
    if not data or len(data) > MAX_STEP_BYTES:
        raise HTTPException(400, "send a STEP file of at most 25 MB as the request body")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "upload.step"
        path.write_bytes(data)
        try:
            return measure_step(path)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc


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
    """The generated parts only: on ar4 the Annin link meshes are in the GLB, not the STEP."""
    path = _design_file(design_id, ".step")
    return FileResponse(path, media_type="application/step", filename=path.name)


@app.get("/designs/{design_id}/fit")
def get_fit(design_id: str) -> dict:
    return json.loads(_design_file(design_id, ".fit.json").read_text())
