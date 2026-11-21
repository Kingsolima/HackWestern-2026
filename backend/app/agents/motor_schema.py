"""TinyAgent output_schema for a motor candidate (HANDOFF-v3 §3 contract).

The JSON file in docs/design/schemas is the source of truth; the Pydantic models mirror it to
validate what the agent returns. Change both together and tell the other owners.
"""

import json
from functools import cache
from typing import Any, Literal

from pydantic import BaseModel

from app.config import REPO_ROOT

SCHEMA_PATH = REPO_ROOT / "docs" / "design" / "schemas" / "motor_candidate.tinyfish.json"

SpecName = Literal[
    "continuous_torque", "peak_torque", "holding_torque", "torque_at_speed",
    "rated_speed", "max_speed",
    "supply_voltage_min", "supply_voltage_max", "rated_voltage", "rated_current",
    "body_length", "shaft_diameter", "price", "lead_time",
]  # fmt: skip


@cache
def output_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text())


class TfSpec(BaseModel):
    name: SpecName
    value: float
    unit: str
    at_speed_value: float | None
    at_speed_unit: str | None
    quote: str
    source_url: str


class TfMotorCandidate(BaseModel):
    status: Literal["success", "blocked", "not_found", "auth_required", "incomplete"]
    reason: str
    manufacturer: str | None
    part_number: str | None
    motor_type: Literal["servo_integrated", "bldc", "stepper", "brushed_dc", "unknown"] | None
    nema_frame: Literal["17", "23", "34", "other"] | None
    specs: list[TfSpec]
    country_of_origin: str | None
    origin_quote: str | None
    origin_source_url: str | None
    product_url: str | None
    datasheet_url: str | None
