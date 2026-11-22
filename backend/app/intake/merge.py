"""Put the sources together: the user's answer wins, then the BOM, then the CAD, then the demo
robot's value."""

from app.intake.schema import (
    SCHEMAS,
    CompanyFact,
    Found,
    IntakeResult,
    RobotKind,
    Source,
    SpecRow,
)
from app.schemas import Robot

TRUST: tuple[Source, ...] = ("answer", "bom", "cad")


def merge(
    kind: RobotKind,
    demo: Robot,
    found: list[Found],
    company: list[CompanyFact] | None = None,
    dropped: list[str] | None = None,
) -> IntakeResult:
    rows: list[SpecRow] = []
    for field in SCHEMAS[kind]:
        default = getattr(demo.requirements, field.robot_field) * field.divisor
        default = round(default, 6)
        best = next(
            (f for source in TRUST for f in found if f.field == field.id and f.source == source),
            None,
        )
        rows.append(
            SpecRow(
                field=field.id,
                label=field.label,
                group=field.group,
                unit=field.unit,
                value=best.value if best else default,
                source=best.source if best else "default",
                evidence=best.evidence if best else None,
                default=default,
                live=field.live,
                ask=field.ask,
                robot_field=field.robot_field,
                divisor=field.divisor,
                integer=field.integer,
                allow_zero=field.allow_zero,
                max=field.max,
            )
        )
    return IntakeResult(robot_kind=kind, company=company or [], specs=rows, dropped=dropped or [])
