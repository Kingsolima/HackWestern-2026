"""Onboarding result -> Project, so an onboarded company gets the same risk map, alternatives
and recommendations as a project file (docs/REMAINING-WORK.md gap 1). Code only: every value is
copied from what the user confirmed, and every fact is "stated"."""

import re

from app.intake.schema import CompanyFact
from app.schemas import BomLine, BomRow, Domain, Project, ProjectFacts, Robot

ONBOARDED_ID = "onboarded"

# First match wins, read against "<category> <part>". Specific words come before general ones:
# a "motor driver" is power electronics, a "wheel encoder" is a sensor.
# (keywords, domain, class in data/research/article_map.yaml or None)
_RULES: tuple[tuple[tuple[str, ...], Domain, str | None], ...] = (
    (("driver", "inverter"), "power", "power_electronics"),
    (("encoder",), "sensing", "encoder"),
    (("lidar",), "sensing", "lidar"),
    (("camera", "sensor", "imu"), "sensing", None),
    (("battery",), "power", "battery_cells"),
    (("harmonic", "strain wave", "strain-wave"), "actuation", "harmonic_drive"),
    (("motor", "servo", "stepper", "actuator"), "actuation", "motor"),
    (("gearbox",), "actuation", None),
    (("computer", "compute", "sbc"), "compute", "compute_platform"),
    (("controller", "mcu", "microcontroller"), "compute", "control_electronics"),
    (
        ("frame", "bracket", "plate", "chassis", "wheel", "enclosure", "fastener"),
        "structure",
        None,
    ),
)
_FRAME = re.compile(r"nema\s*-?\s*(17|23|34)\b", re.IGNORECASE)
_NUMBER = re.compile(r"\d+(?:\.\d+)?")


def classify(row: BomRow) -> tuple[Domain, str | None]:
    text = f"{row.category} {row.part}".lower()
    for keywords, domain, component_class in _RULES:
        if any(k in text for k in keywords):
            return domain, component_class
    return "other", None


def bom_line(n: int, row: BomRow) -> BomLine:
    domain, component_class = classify(row)
    origin = row.origin.strip().upper()
    return BomLine(
        id=f"line_{n}",
        domain=domain,
        qty=row.qty,
        part=row.part,
        unit_price_usd=float(row.unit_cost_usd),
        origin_country=origin if re.fullmatch(r"[A-Z]{2}", origin) else None,
        origin_tier=row.origin_tier,
        hts_code=row.hts_code,
        component_class=component_class,
        stated_risk=row.supply_risk,
    )


def _yes_no(value: str | None) -> bool | None:
    return {"yes": True, "no": False}.get((value or "").strip().lower())


def _number(value: str | None) -> float | None:
    found = _NUMBER.search((value or "").replace(",", ""))
    return float(found.group()) if found else None


def stated_facts(company: list[CompanyFact]) -> ProjectFacts:
    by_field = {c.field: c.value for c in company}
    days = _number(by_field.get("need_by_days"))
    return ProjectFacts(
        sells_to_us_federal=_yes_no(by_field.get("sells_to_us_federal")),
        deploy_countries=[
            c.strip().upper()
            for c in by_field.get("deploy_countries", "").split(",")
            if re.fullmatch(r"[A-Za-z]{2}", c.strip())
        ],
        uptime_critical=_yes_no(by_field.get("uptime_critical")),
        budget_usd=_number(by_field.get("budget_usd")),
        need_by_days=round(days) if days is not None else None,
    )


def project_from_onboarding(company: list[CompanyFact], robot: Robot) -> Project:
    """The robot carries the confirmed drivetrain numbers and the uploaded BOM. The agents work
    on the first motor line; a BOM without one gets a drive-motor line saying so, because the
    drivetrain numbers still describe a motor to source."""
    by_field = {c.field: c.value for c in company}
    bom = [bom_line(n, row) for n, row in enumerate(robot.bom, start=1)]
    deep = next((line for line in bom if line.component_class == "motor"), None)
    if deep is None:
        deep = BomLine(
            id="drive_motor",
            domain="actuation",
            qty=robot.requirements.n_drive_motors,
            part="Drive motor (not in your parts list)",
            component_class="motor",
            notes="Added from the drivetrain answers; price and origin not stated.",
        )
        bom.insert(0, deep)
    frame = _FRAME.search(deep.part)
    kind = by_field.get("kind")
    return Project(
        id=ONBOARDED_ID,
        kind="club" if kind == "club" else "company",
        name=by_field.get("company_name") or "Your company",
        robot=robot.name,
        use_case=by_field.get("use_case", ""),
        robot_kind="wheeled",
        wheeled=robot.requirements,
        deep_line=deep.id,
        deep_frame=frame.group(1) if frame else "23",
        cad_robot="wheeled",
        bom=bom,
        avoid=by_field.get("avoid") or None,
        stated=stated_facts(company),
    )
