"""HTTP API. Stub endpoints the frontend can build against now."""

import json

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.engineering.checks import run_checks
from app.engineering.compliance import ComplianceCard, compliance_card
from app.schemas import CheckResult, DesignVariant, MotorCandidate, Robot

router = APIRouter(prefix="/api")


def load_demo_robot() -> Robot:
    return Robot.model_validate_json((settings.data_dir / "demo_robot.json").read_text())


@router.get("/robot")
def get_robot() -> Robot:
    return load_demo_robot()


@router.get("/compliance")
def get_compliance() -> ComplianceCard:
    return compliance_card(load_demo_robot())


@router.get("/candidates/seed")
def get_seed_candidates() -> list[MotorCandidate]:
    raw = json.loads((settings.data_dir / "seed_motors.json").read_text())
    return [MotorCandidate.model_validate(m) for m in raw["motors"]]


@router.post("/checks")
def post_checks(candidate: MotorCandidate) -> CheckResult:
    return run_checks(candidate, load_demo_robot().requirements)


@router.post("/runs")
def start_run() -> dict:
    # TODO(owner 2): kick off the swarm; return run id + streaming_urls for tiles.
    raise HTTPException(status_code=501, detail="swarm not implemented yet")


@router.get("/designs")
def get_designs() -> list[DesignVariant]:
    # TODO(owner 3): tournament results from Tiger Data design_variants.
    return []
