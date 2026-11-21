"""Shared data contracts. Mirrors docs/ARCHITECTURE.md §4; change both together."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


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


# --- v3 evidence shapes (docs/design/04-architecture.md §4) ---


class Source(BaseModel):
    url: str
    kind: Literal["page", "pdf"]
    fetched_at: datetime
    html_key: str | None = None  # object-storage key of the captured html/pdf
    via: Literal["tinyfetch", "tinyagent", "replay"]


class Claim(BaseModel):
    """One fact, never a bare number. Only the Verifier sets verified=True."""

    candidate_id: str
    field: str  # e.g. "continuous_torque", "price", "country_of_origin"
    raw_value: str
    raw_unit: str | None
    quote: str
    source: Source
    si_value: float | None = None  # filled by units.py, never by an LLM
    extracted_by: Literal["tinyagent", "gemini_text", "gemini_vision"]
    verified: bool = False
    verify_method: Literal["html_quote", "pdf_text", "none"] = "none"
