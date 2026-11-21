"""Compliance card (ARCHITECTURE §3 #2, §6 rules 3–5). Deterministic.

Compliance and supply risk are separate tracks. Unknown origin and allied (e.g. CA) parts
count as foreign. A domestic end product also needs US final assembly.
"""

from decimal import Decimal

from pydantic import BaseModel

from app.schemas import Robot

THRESHOLDS_PCT = (65, 75)


class ComplianceCard(BaseModel):
    domestic_pct: float
    thresholds_pct: tuple[int, ...] = THRESHOLDS_PCT
    us_final_assembly: bool
    supply_risks: list[str]
    notes: list[str]


def compliance_card(robot: Robot) -> ComplianceCard:
    total = sum((r.unit_cost_usd * r.qty for r in robot.bom), Decimal(0))
    domestic = sum(
        (r.unit_cost_usd * r.qty for r in robot.bom if r.origin.upper() == "US"), Decimal(0)
    )
    pct = float(domestic / total * 100) if total else 0.0
    us_assembly = robot.final_assembly_country.upper() == "US"

    notes = ["Not legal advice. COTS treatment: flag for counsel."]
    if not us_assembly:
        notes.append("Also needs US final assembly to be a domestic end product.")

    risks = sorted({f"{r.part}: {r.supply_risk}" for r in robot.bom if r.supply_risk})
    # TODO(owner 3): FCC coverage check.
    return ComplianceCard(
        domestic_pct=round(pct, 1), us_final_assembly=us_assembly, supply_risks=risks, notes=notes
    )
