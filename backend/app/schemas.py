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
    us_first = "us_first"  # the domestic objective; only on when a criteria rule asks for it
    supply_risk = "supply_risk"
    lead_time = "lead_time"


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


# --- v4 shapes (docs/BUILD-PLAN-v4.md section 4): a project, its facts and the criteria code
# derives from them. Additive: jobs without a project run the v3 wheeled pipeline unchanged.

Domain = Literal["actuation", "sensing", "compute", "power", "structure", "other"]
Level = Literal["low", "medium", "high", "unknown"]
FactBasis = Literal["verified", "stated"]
FactField = Literal[
    "sells_to_us_federal", "deploy_countries", "uptime_critical", "budget_usd", "need_by_days"
]
Availability = Literal["in_stock", "lead_time", "out_of_stock", "unknown"]


class ProjectFacts(BaseModel):
    """What the criteria rules read. None / empty = not known, and no rule fires on it."""

    sells_to_us_federal: bool | None = None
    deploy_countries: list[str] = Field(default_factory=list, description="ISO-2 codes")
    uptime_critical: bool | None = None
    budget_usd: float | None = None
    need_by_days: int | None = None


class Fact(BaseModel):
    """Where one ProjectFacts value came from: a quote verified on the team's own page, or the
    team's own statement in the project file."""

    field: FactField
    value: str
    basis: FactBasis
    quote: str | None = None
    source_url: str | None = None


class IntakeSource(BaseModel):
    """A page of the team's own site that INTAKE reads for facts (company projects)."""

    url: str
    reason: str


class ArmLink(BaseModel):
    name: str
    mass_kg: float
    com_m: float = Field(description="Horizontal distance from the joint axis at full extension")


class ArmParams(BaseModel):
    """Inputs of the arm-joint requirement (BUILD-PLAN-v4 section 6), for the deep joint."""

    joint: str
    payload_kg: float
    reach_m: float = Field(description="Joint axis to payload at full horizontal extension")
    links: list[ArmLink]
    gear_ratio: float
    efficiency: float
    omega_max_dps: float = Field(description="Joint top speed, degrees per second")
    t_accel_s: float = Field(description="Time to reach top speed")
    safety_factor: float = 1.5
    bus_voltage_v: float
    illustrative: bool = False
    notes: list[str] = Field(default_factory=list, description="Source or assumption per input")


class BomLine(BaseModel):
    id: str
    domain: Domain
    qty: int
    part: str
    manufacturer: str | None = None
    part_number: str | None = None
    unit_price_usd: float | None = None
    origin_country: str | None = None
    origin_tier: OriginTier = "none"
    availability: Availability = "unknown"
    lead_time_days: int | None = None
    hts_code: str | None = None
    illustrative: bool = False
    sources: list[str] = Field(default_factory=list, description="URLs behind price and origin")
    notes: str | None = None


class Project(BaseModel):
    id: str
    kind: Literal["company", "club"]
    name: str
    robot: str
    use_case: str
    robot_kind: Literal["wheeled", "arm"]
    arm: ArmParams | None = None
    wheeled: RobotRequirements | None = None
    deep_line: str = Field(description="BomLine id the agents work on")
    bom: list[BomLine]
    intake_sources: list[IntakeSource] = Field(default_factory=list)
    stated: ProjectFacts = Field(default_factory=ProjectFacts, description="Team-stated facts")


class CriterionReason(BaseModel):
    rule: str
    fact: FactField | None
    text: str


class Criteria(BaseModel):
    objectives: list[Objective]
    domestic_threshold: float | None = None
    max_lead_time_days: int | None = None
    budget_usd: float | None = None
    duty_countries: list[str] = Field(default_factory=list, description="Whose import duty counts")
    blocking_lists: list[Literal["fcc_covered", "dod_1260h", "uflpa"]] = Field(default_factory=list)
    reasons: list[CriterionReason] = Field(default_factory=list)


RiskFactorName = Literal["sources", "bottleneck", "trade", "restricted", "availability"]


class RiskFactor(BaseModel):
    name: RiskFactorName
    level: Level
    value: str = Field(description="What the level was read from, e.g. '25% US duty'")
    reason: str
    source_urls: list[str] = Field(default_factory=list)


class LineRisk(BaseModel):
    line_id: str
    factors: list[RiskFactor]
    overall: Level = Field(description="Worst known factor; unknown only if every factor is")
    blocked: bool = Field(description="A blocking-list hit, out of stock, or over the need-by")


class Alternative(BaseModel):
    id: str
    line_id: str
    manufacturer: str
    part_number: str
    product_url: str | None = None
    origin_country: str | None = None
    origin_tier: OriginTier = "none"
    unit_price_usd: float | None = None
    availability: Availability = "unknown"
    lead_time_days: int | None = None
    verdict: Literal["pass", "review", "rejected"] | None = Field(
        default=None, description="Spec-check verdict on the deep line; None = no checks run"
    )
    risk: LineRisk
    live: bool = Field(description="Found by a live agent this job, else a sourced research row")


class Recommendation(BaseModel):
    line_id: str
    action: Literal["keep", "dual_source", "re_source"]
    alternative_id: str | None = None
    cost_delta_usd: float | None = Field(
        default=None, description="(alternative - current) unit price x qty; None if unknown"
    )
    risk_before: Level
    risk_after: Level
    blocked: bool = Field(default=False, description="Current part is blocked")
    reason: str
