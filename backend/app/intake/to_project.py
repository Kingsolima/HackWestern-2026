"""Onboarding result -> Project, so an onboarded company gets the same risk map, alternatives
and recommendations as a project file (docs/REMAINING-WORK.md gap 1). Code only: every value is
copied from what the user confirmed, and every fact is "stated"."""

import re
from collections.abc import Sequence

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
# A parts list grouped by subsystem names the domain itself, so "J2 motor support" under
# structure is not read as a motor. The keyword rules then only pick the class. "electronics"
# is not here: it mixes controllers, drivers and cables, which the keyword rules tell apart.
_SUBSYSTEMS: dict[str, Domain] = {
    "actuation": "actuation",
    "transmission": "actuation",  # bearings, belts and pulleys of the joint drives
    "structure": "structure",
    "power": "power",
    "sensors": "sensing",
}
_FRAME = re.compile(r"nema\s*-?\s*(17|23|34)\b", re.IGNORECASE)
_NUMBER = re.compile(r"\d+(?:\.\d+)?")


def classify(row: BomRow) -> tuple[Domain, str | None]:
    text = f"{row.category} {row.part}".lower()
    stated = _SUBSYSTEMS.get(row.category.strip().lower())
    for keywords, domain, component_class in _RULES:
        if any(k in text for k in keywords) and stated in (None, domain):
            return domain, component_class
    return stated or "other", None


def _notes(row: BomRow) -> str | None:
    page = f"Source document page {row.source_page}." if row.source_page else None
    return " ".join(x for x in (page, row.notes) if x) or None


def bom_line(n: int, row: BomRow) -> BomLine:
    domain, component_class = classify(row)
    origin = row.origin.strip().upper()
    return BomLine(
        id=f"line_{n}",
        domain=domain,
        qty=row.qty,
        part=row.part,
        manufacturer=row.supplier or None,
        part_number=row.part_number or None,
        unit_price_usd=float(row.unit_cost_usd) if row.unit_cost_usd is not None else None,
        origin_country=origin if re.fullmatch(r"[A-Z]{2}", origin) else None,
        origin_tier=row.origin_tier,
        availability=row.availability,
        lead_time_days=row.lead_time_days,
        hts_code=row.hts_code,
        component_class=component_class,
        stated_risk=row.supply_risk,
        notes=_notes(row),
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


def _same_part(a: str | None, b: str | None) -> bool:
    return bool(a and b) and a.strip().casefold() == b.strip().casefold()


# Researched fields of a reference line that fill what the uploaded row left unknown.
_RESEARCHED = ("unit_price_usd", "origin_country", "hts_code", "lead_time_days")


def known_arm(bom: list[BomLine], references: Sequence[Project]) -> tuple[Project, int] | None:
    """(reference project, index of the matching line) when the parts list holds the motor a
    researched arm project works on, matched by part number. The wheeled drivetrain numbers
    cannot describe an arm joint, so such a BOM runs on the reference's joint parameters."""
    for ref in references:
        if ref.robot_kind != "arm" or ref.arm is None:
            continue
        ref_deep = next(line for line in ref.bom if line.id == ref.deep_line)
        for i, line in enumerate(bom):
            if _same_part(line.part_number, ref_deep.part_number):
                return ref, i
    return None


def _with_research(line: BomLine, ref: BomLine, ref_name: str) -> BomLine:
    """The uploaded line, with the reference line's researched values where it had none."""
    fill: dict[str, object] = {
        f: getattr(ref, f) for f in _RESEARCHED if getattr(line, f) is None and getattr(ref, f)
    }
    if line.origin_country is None and ref.origin_country:
        fill["origin_tier"] = ref.origin_tier
    if line.availability == "unknown":
        fill["availability"] = ref.availability
    note = f"{', '.join(sorted(fill))} from the research on {ref_name}, not from your parts list."
    return line.model_copy(
        update={
            **fill,
            "component_class": ref.component_class,
            "sources": ref.sources,
            "notes": " ".join(x for x in (line.notes, note if fill else None) if x) or None,
        }
    )


def project_from_onboarding(
    company: list[CompanyFact], robot: Robot, references: Sequence[Project] = ()
) -> Project:
    """The robot carries the confirmed drivetrain numbers and the uploaded BOM. The agents work
    on the first motor line; a BOM without one gets a drive-motor line saying so, because the
    drivetrain numbers still describe a motor to source. A BOM that holds the motor of a
    researched arm project (`references`) runs as that arm instead: see known_arm."""
    by_field = {c.field: c.value for c in company}
    bom = [bom_line(n, row) for n, row in enumerate(robot.bom, start=1)]
    kind = by_field.get("kind")
    common = {
        "id": ONBOARDED_ID,
        "kind": "club" if kind == "club" else "company",
        "name": by_field.get("company_name") or "Your company",
        "robot": robot.name,
        "use_case": by_field.get("use_case", ""),
        "avoid": by_field.get("avoid") or None,
        "stated": stated_facts(company),
    }
    arm = known_arm(bom, references)
    if arm is not None:
        ref, i = arm
        ref_deep = next(line for line in ref.bom if line.id == ref.deep_line)
        bom[i] = _with_research(bom[i], ref_deep, ref.robot)
        return Project(
            **common,
            robot_kind="arm",
            arm=ref.arm,
            deep_line=bom[i].id,
            deep_frame=ref.deep_frame,
            cad_robot=ref.cad_robot,
            bom=bom,
        )
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
    return Project(
        **common,
        robot_kind="wheeled",
        wheeled=robot.requirements,
        deep_line=deep.id,
        deep_frame=frame.group(1) if frame else "23",
        cad_robot="wheeled",
        bom=bom,
    )
