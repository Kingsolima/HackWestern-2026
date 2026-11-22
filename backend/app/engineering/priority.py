"""Risk priority per part and the action it leads to. Code only; every score lists the evidence
it was read from and the evidence that is missing.

    priority = supply + customer + impact      each 0-3, or unknown

- supply:   how exposed the part is in general (availability, concentration, duty, sources).
- customer: whether the part conflicts with what THIS customer said it must avoid or comply
            with. A part nobody objected to scores 0 here, whatever it is made of.
- impact:   how badly the robot is hurt when the part cannot be had.

Unknown is never 0. An unknown score adds nothing to the low end of the range and 3 to the high
end, and missing evidence on a part that matters leads to "investigate", not to "keep".
"""

import re

from app.schemas import (
    Alternative,
    BomLine,
    Concern,
    Criteria,
    Dependency,
    Domain,
    Level,
    LineRisk,
    Priority,
    Recommendation,
    Score,
)

HIGH, MEDIUM = 6, 3  # level reads the low end: high >= 6, medium 3-5, low <= 2

# How badly the robot is hurt without the part, by what the part does.
IMPACT: dict[Domain, tuple[int, str]] = {
    "actuation": (3, "the robot cannot move without it"),
    "power": (3, "the robot cannot run without it"),
    "compute": (3, "the robot cannot run without it"),
    "sensing": (2, "the robot runs degraded without it"),
    "structure": (1, "a standard or machinable part"),
    "other": (1, "a standard part"),
}
MISSING_SUPPLY = {
    "trade": "import duty (no customs code on this line)",
    "availability": "stock and lead time",
    "bottleneck": "how concentrated supply is for this kind of part",
    "sources": "how many alternatives exist",
}


def level_of(lo: int) -> Level:
    return "high" if lo >= HIGH else "medium" if lo >= MEDIUM else "low"


def supply_score(risk: LineRisk) -> Score:
    """From the supply factors (the blocking lists count under customer, not here)."""
    factors = [f for f in risk.factors if f.name != "restricted"]
    known = [f for f in factors if f.level != "unknown"]
    missing = [MISSING_SUPPLY[f.name] for f in factors if f.level == "unknown"]
    if not known:
        return Score(value=None, basis="unknown", missing=missing)
    if any(f.name == "availability" and f.level == "high" for f in known):
        value = 3
    elif any(f.level == "high" for f in known):
        value = 2
    elif any(f.level == "medium" for f in known):
        value = 1
    else:
        value = 0
    reasons = [f"{f.name}: {f.value}" for f in known if f.level != "low"] or [
        "nothing of concern in " + ", ".join(f.name for f in known)
    ]
    return Score(value=value, reasons=reasons, missing=missing)


def impact_score(domain: Domain, criteria: Criteria) -> Score:
    value, why = IMPACT[domain]
    reasons = [f"{domain}: {why}"]
    if criteria.uptime_critical and value == 2:
        value = 3
        reasons.append("you said downtime is costly")
    return Score(value=value, reasons=reasons)


def _words(text: str) -> set[str]:
    return {w for w in re.split(r"[^a-z]+", text.casefold()) if len(w) >= 5}


def _concern(c: Concern, line: BomLine, dep: Dependency | None) -> tuple[int | None, str, str]:
    """(value or None, basis, sentence) for one concern against one part."""
    origin = line.origin_country
    if c.kind == "country":
        if origin is None:
            return None, "unknown", f"country of origin (you want to avoid {c.label})"
        if origin == c.country:
            return 3, "stated", f"made in {origin}, and you want to avoid {c.label}"
        return 0, "stated", f"made in {origin}, not {c.country}"
    if c.kind == "supplier":
        if not line.manufacturer:
            return None, "unknown", f"who makes it (you want to avoid {c.label})"
        if c.label.casefold() in line.manufacturer.casefold():
            return 3, "stated", f"made by {line.manufacturer}, which you want to avoid"
        return 0, "stated", f"made by {line.manufacturer}"
    # material
    if line.stated_risk and _words(line.stated_risk) & _words(c.label):
        return 3, "stated", f"your parts list marks this line '{line.stated_risk}' ({c.label})"
    if dep is None or dep.depends == "unknown":
        return None, "unknown", f"whether this part depends on {c.label}"
    if dep.depends == "unlikely":
        return 0, "inferred", f"unlikely to depend on {c.label} (inferred from the part class)"
    inferred = f"likely depends on {c.label} (inferred from the part class, not verified"
    inferred += f": {dep.why})" if dep.why else ")"
    if c.country is None:
        return 2, "inferred", inferred
    if origin is None:
        return None, "unknown", f"country of origin ({inferred})"
    if origin == c.country:
        return 2, "inferred", f"{inferred} and is made in {origin}"
    return (
        None,
        "unknown",
        f"where its {c.label} come from: the part is made in {origin}, "
        "the material's origin is not verified",
    )


def customer_score(
    line: BomLine, risk: LineRisk, criteria: Criteria, deps: list[Dependency]
) -> Score:
    """Only what this customer stated, or what their situation requires, can score here."""
    found: list[tuple[int | None, str, str]] = []
    hits = next((f for f in risk.factors if f.name == "restricted" and f.level == "high"), None)
    if hits is not None:
        found.append((3, "stated", f"supplier on a blocking list: {hits.value}"))
    if criteria.domestic_threshold is not None:
        if line.origin_country is None:
            found.append((None, "unknown", "country of origin (federal buyers need US content)"))
        elif line.origin_country != "US":
            found.append(
                (
                    2,
                    "rule",
                    "you sell to US federal buyers, who need mostly US content, and it is made in "
                    f"{line.origin_country}",
                )
            )
        else:
            found.append((0, "rule", "made in the US"))
    by_concern = {d.concern_id: d for d in deps}
    for c in criteria.concerns:
        found.append(_concern(c, line, by_concern.get(c.id)))
    if criteria.concerns_unread:
        found.append((None, "unknown", "what you want to avoid (your answer could not be read)"))

    if not found:
        return Score(value=0, reasons=["you stated no concern that applies to parts"])
    known = [f for f in found if f[0] is not None]
    missing = [f[2] for f in found if f[0] is None]
    top = max(known, key=lambda f: f[0], default=None)
    if top is not None and top[0] >= 2:
        hot = [f for f in known if f[0] >= 2]
        return Score(value=top[0], basis=top[1], reasons=[f[2] for f in hot], missing=missing)
    if missing:
        return Score(value=None, basis="unknown", reasons=[f[2] for f in known], missing=missing)
    return Score(value=0, basis=top[1] if top else "rule", reasons=[f[2] for f in known])


def priority(line: BomLine, risk: LineRisk, criteria: Criteria, deps: list[Dependency]) -> Priority:
    scores = (
        supply_score(risk),
        customer_score(line, risk, criteria, deps),
        impact_score(line.domain, criteria),
    )
    lo = sum(s.value or 0 for s in scores)
    hi = sum(3 if s.value is None else s.value for s in scores)
    return Priority(
        supply=scores[0], customer=scores[1], impact=scores[2], lo=lo, hi=hi, level=level_of(lo)
    )


def _name(a: Alternative) -> str:
    return f"{a.manufacturer} {a.part_number}"


def _open_points(a: Alternative) -> list[str]:
    """What is not yet proven about an alternative."""
    points = []
    if a.verdict != "pass":
        points.append("its specs are not all verified" if a.verdict == "review" else "no checks")
    if a.risk.priority and a.risk.priority.customer.value is None:
        points += a.risk.priority.customer.missing
    return points


def decide(line: BomLine, current: LineRisk, alternatives: list[Alternative]) -> Recommendation:
    """The action for one part. Rules, first match wins:

    1. re_source   a documented conflict (customer score 3, or the part is blocked) AND an
                   alternative that passed every check, is not blocked and has customer score 0.
    2. investigate a conflict (customer score >= 2, or blocked) with no such alternative. The
                   reason names the best candidate and what is unproven about it.
    3. investigate the customer score is unknown: we cannot tell whether the part conflicts.
    4. investigate no supply evidence at all on a part with impact >= 2 whose range reaches high.
    5. dual_source no conflict, supply score >= 2 and priority at least medium.
    6. keep        otherwise.
    """
    p = current.priority
    assert p is not None, "decide() needs a line scored by priority()"
    usable = [a for a in alternatives if a.verdict != "rejected" and not a.risk.blocked]
    passed = [a for a in usable if a.verdict == "pass"]

    def lo(a: Alternative) -> int:
        return a.risk.priority.lo if a.risk.priority else 9

    def order(a: Alternative) -> tuple:
        price = a.unit_price_usd
        return (a.verdict != "pass", lo(a), price is None, price or 0.0, a.id)

    def delta(a: Alternative) -> float | None:
        if a.unit_price_usd is None or line.unit_price_usd is None:
            return None
        return (a.unit_price_usd - line.unit_price_usd) * line.qty

    def out(action, reason: str, a: Alternative | None = None, moved: bool = False):
        after = a.risk.priority.level if (moved and a and a.risk.priority) else p.level
        return Recommendation(
            line_id=line.id,
            action=action,
            alternative_id=a.id if a else None,
            cost_delta_usd=delta(a) if a else None,
            risk_before=p.level,
            risk_after=after,
            blocked=current.blocked,
            priority_lo=p.lo,
            priority_hi=p.hi,
            reason=reason,
        )

    c = p.customer.value
    why = "; ".join(p.customer.reasons) or "the part is blocked (out of stock or past need-by)"
    if current.blocked or (c is not None and c >= 2):
        label = "Conflict" if (current.blocked or c == 3) else "Concern"
        clean = [
            a for a in passed if a.risk.priority is None or a.risk.priority.customer.value == 0
        ]
        if (current.blocked or c == 3) and clean:
            a = min(clean, key=order)
            return out(
                "re_source",
                f"Conflict: {why}. {_name(a)} passed every check and has no such conflict.",
                a,
                moved=True,
            )
        if usable:
            a = min(usable, key=order)
            open_points = _open_points(a)
            if p.customer.basis == "inferred":
                open_points.insert(0, "the conflict itself is inferred, so confirm it first")
            return out(
                "investigate",
                f"{label}: {why}. Best candidate so far: {_name(a)}. "
                f"Before switching: {'; '.join(open_points) or 'confirm the conflict'}.",
                a,
            )
        return out("investigate", f"{label}: {why}. No alternative was searched for this part.")
    if c is None:
        return out(
            "investigate",
            "Cannot tell yet whether this part conflicts with what you need. Missing: "
            + "; ".join(p.customer.missing)
            + ".",
        )
    if p.supply.value is None and (p.impact.value or 0) >= 2 and p.hi >= HIGH:
        return out(
            "investigate",
            "No supply evidence for a part the robot depends on. Missing: "
            + "; ".join(p.supply.missing)
            + ".",
        )
    if (p.supply.value or 0) >= 2 and p.lo >= MEDIUM:
        exposure = "; ".join(p.supply.reasons)
        if passed:
            a = min(passed, key=order)
            return out(
                "dual_source",
                f"The part is fine for you, but supply is exposed ({exposure}). "
                f"{_name(a)} passed every check: add it as a second source.",
                a,
            )
        return out(
            "dual_source",
            f"The part is fine for you, but supply is exposed ({exposure}). "
            "Find a second source; none has been checked in this run.",
        )
    gaps = p.supply.missing
    note = f" Not checked: {'; '.join(gaps)}." if gaps else ""
    return out("keep", "No known concern needs action." + note)


_ACTION_ORDER = {"re_source": 0, "dual_source": 1, "investigate": 2, "keep": 3}


def rank(recs: list[Recommendation]) -> list[Recommendation]:
    """Parts that need action first, highest priority first; keeps last."""

    def key(r: Recommendation) -> tuple:
        return (
            r.action == "keep",
            -(r.priority_lo or 0),
            -(r.priority_hi or 0),
            _ACTION_ORDER[r.action],
            r.line_id,
        )

    return sorted(recs, key=key)
