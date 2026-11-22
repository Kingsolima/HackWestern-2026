from dataclasses import dataclass, field

from app.orchestrator.board import Board
from app.orchestrator.cad import CadClient
from app.orchestrator.events import EventLog
from app.orchestrator.fleet import Fleet, JobBudget
from app.schemas import Claim, JobMode, Robot
from app.tfclient.client import TFClient


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
    raw_claims: list[Claim] = field(default_factory=list)
    facts: list[Claim] = field(default_factory=list)
    cad: CadClient | None = None  # None: BUILD reports that no CAD worker is configured
