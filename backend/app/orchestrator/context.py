from dataclasses import dataclass, field

from app.agents.triage import Lead
from app.cad_client import CadBuild, CadClient
from app.engineering.spec_checks import FitBadge, SpecCheck, Verdict
from app.orchestrator.board import Board
from app.orchestrator.events import EventLog
from app.orchestrator.fleet import Fleet, JobBudget
from app.schemas import (
    Alternative,
    Candidate,
    Claim,
    Criteria,
    Fact,
    JobMode,
    LineRisk,
    Objective,
    Project,
    Robot,
)
from app.tfclient.client import TFClient
from app.tfclient.gemini import GeminiClient


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
    gemini: GeminiClient
    candidates: list[Candidate] = field(default_factory=list)
    facts: list[Claim] = field(default_factory=list)
    queries: list[str] = field(default_factory=list)
    leads: list[Lead] = field(default_factory=list)
    designs: list[Design] = field(default_factory=list)
    project: Project | None = None  # None: the v3 wheeled demo job
    verified_facts: list[Fact] = field(default_factory=list)
    criteria: Criteria | None = None
    line_risks: dict[str, LineRisk] = field(default_factory=dict)
    alternatives: list[Alternative] = field(default_factory=list)
