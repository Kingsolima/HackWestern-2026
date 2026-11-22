"""Shared data contracts. Mirrors docs/ARCHITECTURE.md §4; change both together."""

from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, Field, model_validator

OriginTier = Literal["T1", "T2", "T3", "rejected", "none"]
Outcome = Literal["success", "blocked", "not_found", "auth_required", "incomplete", "error"]
TfStatus = Literal["PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"]
Product = Literal["search", "fetch", "agent", "browser", "monitor", "gemini"]
JobMode = Literal["live", "replay", "mixed"]
MotorType = Literal["servo_integrated", "bldc", "stepper", "brushed_dc", "unknown"]
NemaFrameName = Literal["17", "23", "34", "other"]
SpecName = Literal[
    "continuous_torque",
    "peak_torque",
    "holding_torque",
    "torque_at_speed",
    "rated_speed",
    "max_speed",
    "supply_voltage_min",
    "supply_voltage_max",
    "rated_voltage",
    "rated_current",
    "body_length",
    "shaft_diameter",
    "price",
    "lead_time",
]
VerifyMethod = Literal["html_quote", "pdf_text", "agent_dom"]
ExtractedBy = Literal["tinyagent", "gemini_text", "gemini_vision"]
Via = Literal["tinyfetch", "tinyagent", "replay"]


class RobotRequirements(BaseModel):
    mass_kg: float = Field(description="Robot mass including payload")
    wheel_radius_m: float
    n_drive_motors: int
    gear_ratio: float = Field(description="G")
    efficiency: float = Field(description="Drivetrain efficiency η")
    crr: float = Field(description="Rolling resistance coefficient")
    max_slope_deg: float = Field(description="θ")
    accel_mps2: float = Field(description="Target acceleration a")
    v_max_mps: float = Field(description="Top speed")
    bus_voltage_v: float
    envelope_mm: float = Field(description="Space available for motor + bracket")
    safety_factor: float = 1.5


class BomRow(BaseModel):
    part: str
    category: str
    qty: int
    unit_cost_usd: Decimal
    origin: str = Field(description="ISO country code or 'unknown' (unknown counts as foreign)")
    supply_risk: str | None = Field(
        default=None, description="e.g. ndfeb_magnets. Shown separately; never changes domestic %"
    )
    origin_tier: OriginTier = Field(
        default="none", description="Only T1/T2 with country US count as domestic"
    )
    freight_usd: Decimal | None = Field(default=None, description="None = not known yet")
    duty_usd: Decimal | None = Field(default=None, description="None = not known yet")
    hts_code: str | None = None


class Robot(BaseModel):
    name: str
    final_assembly_country: str
    requirements: RobotRequirements
    bom: list[BomRow]


class AgentStatus(StrEnum):
    success = "success"
    blocked = "blocked"
    not_found = "not_found"
    auth_required = "auth_required"
    incomplete = "incomplete"


class MotorCandidate(BaseModel):
    """TinyFish agent output_schema. Data fields are optional on purpose: no placeholders."""

    status: AgentStatus
    reason: str
    manufacturer: str | None = None
    part_number: str | None = None
    nema_frame: str | None = Field(default=None, description="17 | 23 | 34")
    body_length_mm: float | None = None
    rated_torque_nm: float | None = None
    rated_speed_rpm: float | None = None
    voltage_v: float | None = None
    shaft_diameter_mm: float | None = None
    price_usd: float | None = None
    lead_time_days: float | None = None
    country_of_origin: str | None = None
    origin_quote: str | None = Field(default=None, description="Exact text from the page")
    product_url: str | None = None
    datasheet_url: str | None = None


class VerifierStatus(StrEnum):
    verified = "verified"
    price_mismatch = "price_mismatch"
    origin_not_found = "origin_not_found"
    frame_mismatch = "frame_mismatch"
    blocked = "blocked"
    rejected = "rejected"


class Verdict(StrEnum):
    rejected = "rejected"
    review = "review"
    passed = "pass"


class Fit(StrEnum):
    drop_in = "drop_in"
    close = "close"
    needs_review = "needs_review"


class CheckRow(BaseModel):
    check: str
    value: float | None
    threshold: float | None
    passed: bool | None = Field(description="None = data missing → Review")
    sources: list[str] = []


class CheckResult(BaseModel):
    candidate: str
    verdict: Verdict
    fit: Fit
    rows: list[CheckRow]


class Objective(StrEnum):
    cost = "cost"
    performance = "performance"
    us_first = "us_first"


class DesignVariant(BaseModel):
    design_id: str
    objective: Objective
    motor: str
    cost_usd: Decimal
    domestic_pct: float
    glb_url: str | None = None
    step_url: str | None = None


# --- v3 shapes (docs/design/04-architecture.md section 4). Additive: the flat MotorCandidate
# above stays until the frontend moves to these in one coordinated change.


class Spec(BaseModel):
    name: SpecName
    value: float
    unit: str
    at_speed_value: float | None
    at_speed_unit: str | None
    quote: str
    source_url: str


class AgentMotorCandidate(BaseModel):
    """TinyAgent output. Mirrors docs/design/schemas/motor_candidate.tinyfish.json."""

    status: AgentStatus
    reason: str
    manufacturer: str | None
    part_number: str | None
    motor_type: MotorType | None
    nema_frame: NemaFrameName | None
    specs: list[Spec]
    country_of_origin: str | None
    origin_quote: str | None
    origin_source_url: str | None
    product_url: str | None
    datasheet_url: str | None


class Source(BaseModel):
    url: str
    kind: Literal["page", "pdf"]
    fetched_at: datetime
    html_key: str | None = Field(default=None, description="Storage key of the captured html/pdf")
    via: Via
    run_id: str | None = Field(default=None, description="TinyAgent run that read this page")


class Claim(BaseModel):
    """One fact as the page states it. Never a bare number."""

    id: str
    candidate_id: str
    field: str = Field(description="e.g. continuous_torque, country_of_origin")
    raw_value: str
    raw_unit: str | None
    quote: str
    source: Source
    si_value: float | None = Field(default=None, description="Set by units code, never an LLM")
    extracted_by: ExtractedBy
    verified: bool = False
    verify_method: Literal["html_quote", "pdf_text", "agent_dom", "none"] = "none"


class OriginEvidence(BaseModel):
    country: str | None
    tier: OriginTier
    claim_id: str | None


class Candidate(BaseModel):
    id: str
    manufacturer: str | None
    part_number: str | None
    motor_type: MotorType
    nema_frame: NemaFrameName | None
    claims: list[Claim]
    origin: OriginEvidence
    status: Literal["found", "blocked", "not_found", "auth_required", "incomplete"]
    product_url: str | None = None


class AgentRunResult(BaseModel):
    """A finished TinyAgent run as code sees it; the input to classify_outcome."""

    run_id: str
    tf_status: TfStatus
    result: dict[str, Any] | None = Field(description="Parsed output_schema JSON, if any")
    error: str | None = None
    profile_hint_reason: Literal["auth_wall", "bot_challenge"] | None = None
    page_text: str | None = Field(default=None, description="Last captured page text, if any")
    steps: int | None = None
    duration_s: float = 0.0


class RunRecord(BaseModel):
    """One per external call; goes to Tiger Data agent_runs."""

    run_id: str
    job_id: str
    product: Product
    site: str
    started_at: datetime
    duration_s: float
    tf_status: TfStatus | None
    outcome: Outcome
    reason: str
    steps: int | None
    cost_usd_est: float | None
    live: bool


BoardKind = Literal["fact", "hint", "supplier", "gap_request"]


class BoardEntry(BaseModel):
    """A row of the shared board (docs/design/07 section 3)."""

    time: datetime = Field(default_factory=lambda: datetime.now(UTC))
    job_id: str
    author: str = Field(description="e.g. swap:drive_motor, origin:battery, verifier, critic")
    bom_line: str | None = Field(default=None, description="None = relevant to every line")
    kind: BoardKind
    subject: str = Field(description="Domain, manufacturer or candidate id")
    payload: dict[str, Any]
    claim_id: str | None = None
    verified: bool = False

    VERIFIER: ClassVar[str] = "verifier"

    @model_validator(mode="after")
    def _only_verifier_writes_facts(self) -> "BoardEntry":
        if self.kind == "fact" and not (self.verified and self.author == self.VERIFIER):
            raise ValueError("only the verifier writes verified facts")
        return self
