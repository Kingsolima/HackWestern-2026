from dataclasses import dataclass, field

from app.cad_client import CadBuild, CadClient
from app.engineering.spec_checks import FitBadge, SpecCheck, Verdict
from app.orchestrator.board import Board
from app.orchestrator.events import EventLog
from app.orchestrator.fleet import Fleet, JobBudget
from app.schemas import Candidate, Claim, JobMode, Objective, Robot
from app.tfclient.client import TFClient


@dataclass
class Design:
    """A checked candidate and its bracket build."""

    design_id: str
    candidate: Candidate
    checks: list[SpecCheck]
    verdict: Verdict
    fit_badge: FitBadge | None
    price_usd: float | None
    build: CadBuild | None
    objectives: list[Objective] = field(default_factory=list)


@dataclass
class JobContext:
    """Everything one job's stages and workers share."""

    job_id: str
    mode: JobMode
    robot: Robot
    log: EventLog
    tf: TFClient
    fleet: Fleet
    budget: JobBudget
    board: Board
    cad: CadClient
    candidates: list[Candidate] = field(default_factory=list)
    facts: list[Claim] = field(default_factory=list)
    designs: list[Design] = field(default_factory=list)
