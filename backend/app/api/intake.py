"""Intake API: turn the onboarding's files and open answers into the specs review screen.

    POST /api/intake      {robot_kind, bom, cad?, answers?} -> company facts + one row per spec
    POST /api/intake/cad  STEP bytes -> what the CAD worker measured (pass it back as `cad`)
    GET  /api/intake/example  the recorded example answers

Without `answers` only the BOM and CAD rules run, which tells the page what is still missing.
With answers, Gemini reads them once and code confirms every item (app/intake/extract.py).
"""

from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel

from app.api.jobs import get_runtime, require_live_permission
from app.api.routes import load_demo_robot
from app.cad_client import CadError
from app.config import settings as runtime_settings
from app.intake.extract import confirm, prompt, response_schema
from app.intake.from_bom import specs_from_bom
from app.intake.from_cad import specs_from_cad
from app.intake.merge import merge
from app.intake.schema import SCHEMAS, Answers, CadMeasure, IntakeResult, RobotKind, SpecField
from app.orchestrator.fleet import JobBudget
from app.orchestrator.runtime import Runtime
from app.schemas import BomRow
from app.tfclient.recorder import ReplayMiss

router = APIRouter(prefix="/api/intake")
MAX_STEP_BYTES = 25 * 1024 * 1024


class IntakeRequest(BaseModel):
    robot_kind: RobotKind = "wheeled"
    bom: list[BomRow] = []
    cad: CadMeasure | None = None
    answers: Answers | None = None


def load_example() -> Answers:
    path = runtime_settings.data_dir / "onboarding_example.json"
    return Answers.model_validate_json(path.read_text())


async def read_answers(
    answers: Answers, fields: tuple[SpecField, ...], runtime: Runtime, token: str | None
) -> dict[str, Any]:
    """A recorded reading when these exact answers were read before (the demo example replays
    offline); otherwise one real Gemini call, which on a public deploy needs the live token."""
    text, schema = prompt(answers, fields), response_schema(fields)
    try:
        return await runtime.gemini("replay").extract_json(text, schema)
    except ReplayMiss:
        pass
    require_live_permission("mixed", token, runtime)
    if not runtime.settings.gemini_api_key:
        raise HTTPException(503, "GEMINI_API_KEY is not set, so new answers cannot be read")
    try:
        async with runtime.fleet.slot("gemini", JobBudget()):
            return await runtime.gemini("mixed").extract_json(text, schema)
    except (httpx.HTTPError, ValueError, KeyError, IndexError) as exc:
        raise HTTPException(
            502, f"Gemini could not read the answers ({type(exc).__name__})"
        ) from exc


@router.post("")
async def intake(
    body: IntakeRequest,
    runtime: Annotated[Runtime, Depends(get_runtime)],
    x_live_token: Annotated[str | None, Header()] = None,
) -> IntakeResult:
    fields = SCHEMAS[body.robot_kind]
    found = specs_from_bom(body.bom) + (specs_from_cad(body.cad) if body.cad else [])
    company, dropped = [], []
    if body.answers and body.answers.text().strip():
        raw = await read_answers(body.answers, fields, runtime, x_live_token)
        company, stated, dropped = confirm(raw, body.answers, fields)
        found += stated
    return merge(body.robot_kind, load_demo_robot(), found, company, dropped)


@router.get("/example")
def example() -> Answers:
    """The answers behind "Use the example". Their reading is recorded, and their numbers are
    the demo robot's, so the whole demo replays offline (tests/test_onboarding_intake.py keeps that true)."""
    return load_example()


@router.post("/cad")
async def intake_cad(
    request: Request, runtime: Annotated[Runtime, Depends(get_runtime)]
) -> CadMeasure:
    data = await request.body()
    if not data:
        raise HTTPException(400, "the file is empty")
    if len(data) > MAX_STEP_BYTES:
        raise HTTPException(413, "the STEP file is over 25 MB")
    try:
        return await runtime.cad.measure(data)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except CadError as exc:
        raise HTTPException(502, str(exc)) from exc
