"""Intake: what a robot kind needs to know, and the shapes the intake API returns.

One entry in SCHEMAS per robot kind. A field's value is found, in order of trust, in the user's
answer, the BOM, the CAD file, and last the demo robot's value. Adding the arm joint
(BUILD-PLAN-v4 section 6) is one more entry here plus its rules in from_bom / from_cad.
"""

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict

RobotKind = Literal["wheeled"]
Source = Literal["answer", "bom", "cad", "default"]
# What a number measures: picks the unit table in extract.py.
Quantity = Literal[
    "mass", "length", "speed", "accel", "angle", "voltage", "fraction", "plain", "money", "days"
]


@dataclass(frozen=True)
class SpecField:
    id: str
    label: str
    group: str
    unit: str
    quantity: Quantity
    robot_field: str
    """RobotRequirements field this fills: robot value = value / divisor."""
    divisor: float = 1.0
    live: bool = False
    """True when the value ends up in the agent's goal (engineering/spec_checks.py requirement,
    agents/targets.py goal_for): changing it means real agent runs, not a replay."""
    ask: str | None = None
    """How the open question names it when it is still missing. None = never asked for."""
    hint: str = ""
    """Extra guidance for the extractor."""
    integer: bool = False
    allow_zero: bool = False
    max: float | None = None


WHEELED: tuple[SpecField, ...] = (
    SpecField(
        "n_drive_motors", "Drive motors", "Drivetrain", "", "plain", "n_drive_motors",
        live=True, ask="how many drive motors it has", integer=True, max=16,
    ),
    SpecField(
        "gear_ratio", "Gear ratio", "Drivetrain", ": 1", "plain", "gear_ratio",
        live=True, ask="the gear ratio between motor and wheel", max=1000,
        hint="motor turns per wheel turn; direct drive is 1",
    ),
    SpecField(
        "wheel_radius_mm", "Wheel radius", "Drivetrain", "mm", "length", "wheel_radius_m",
        divisor=1000, live=True, ask="the drive wheel size", max=2000,
    ),
    SpecField(
        "envelope_mm", "Space for motor and bracket", "Drivetrain", "mm", "length",
        "envelope_mm", ask="how much space there is for the motor and its bracket", max=2000,
    ),
    SpecField(
        "efficiency", "Drivetrain efficiency", "Drivetrain", "", "fraction", "efficiency",
        live=True, max=1,
    ),
    SpecField(
        "mass_kg", "Mass with payload", "Load and motion", "kg", "mass", "mass_kg",
        live=True, ask="its total mass with payload", max=100000,
        hint="the whole robot including what it carries",
    ),
    SpecField(
        "v_max_mps", "Top speed", "Load and motion", "m/s", "speed", "v_max_mps",
        ask="its top speed", max=100,
    ),
    SpecField(
        "max_slope_deg", "Steepest slope", "Load and motion", "deg", "angle", "max_slope_deg",
        live=True, ask="the steepest slope it climbs", allow_zero=True, max=60,
    ),
    SpecField(
        "accel_mps2", "Acceleration", "Load and motion", "m/s²", "accel", "accel_mps2",
        live=True, ask="how fast it accelerates", allow_zero=True, max=100,
    ),
    SpecField(
        "crr", "Rolling resistance", "Load and motion", "", "fraction", "crr", live=True, max=1
    ),
    SpecField(
        "safety_factor", "Safety factor", "Load and motion", "", "plain", "safety_factor",
        live=True, max=10,
    ),
    SpecField(
        "bus_voltage_v", "Bus voltage", "Power", "V", "voltage", "bus_voltage_v",
        live=True, ask="the bus voltage", max=1000,
    ),
)  # fmt: skip

SCHEMAS: dict[RobotKind, tuple[SpecField, ...]] = {"wheeled": WHEELED}


class Found(BaseModel):
    """One value a rule or the extractor found, before the merge picks a winner."""

    field: str
    value: float
    source: Source
    evidence: str


class SpecRow(BaseModel):
    """One line of the specs review screen. `default` is the demo robot's value, so the browser
    can tell whether a live field still matches the recordings."""

    field: str
    label: str
    group: str
    unit: str
    value: float
    source: Source
    evidence: str | None
    default: float
    live: bool
    ask: str | None
    robot_field: str
    divisor: float
    integer: bool
    allow_zero: bool
    max: float | None


class CompanyFact(BaseModel):
    """Stated by the user, never checked against anything but their own words."""

    field: str
    label: str
    value: str
    quote: str


class CadPart(BaseModel):
    name: str
    bbox_mm: tuple[float, float, float]
    volume_mm3: float


class CadMeasure(BaseModel):
    """What the CAD worker read from an uploaded STEP file (cad/cad_worker/measure.py)."""

    parts: list[CadPart]
    bbox_mm: tuple[float, float, float]
    volume_mm3: float


class Answers(BaseModel):
    """The four open answers. Outer whitespace is dropped, so a stray newline does not turn a
    recorded reading into a new Gemini call."""

    model_config = ConfigDict(str_strip_whitespace=True)

    who: str = ""
    market: str = ""
    limits: str = ""
    drivetrain: str = ""

    def text(self) -> str:
        return "\n\n".join(a for a in (self.who, self.market, self.limits, self.drivetrain) if a)


class IntakeResult(BaseModel):
    robot_kind: RobotKind
    company: list[CompanyFact]
    specs: list[SpecRow]
    dropped: list[str]
    """Things the extractor returned that code could not confirm, in plain words."""
