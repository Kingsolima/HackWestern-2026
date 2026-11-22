"""Tournament (docs/design/04 section 3, RANK): best design per objective. Deterministic.

Eligible: Pass* designs, or Review designs when nothing passes; Rejected never ranks. A design
missing the number an objective needs (price, torque margin) cannot win that objective.
"""

from pydantic import BaseModel

from app.engineering.spec_checks import SpecCheck, Verdict
from app.schemas import Objective, OriginTier


class RankInput(BaseModel):
    candidate_id: str
    verdict: Verdict
    price_usd: float | None
    origin_tier: OriginTier
    checks: list[SpecCheck]


_TIER_ORDER: dict[OriginTier, int] = {"T1": 0, "T2": 1, "T3": 2, "none": 3, "rejected": 4}


def _torque_margin(d: RankInput) -> float | None:
    margins = [c.margin for c in d.checks if c.check == "torque_cont" and c.margin is not None]
    return margins[0] if margins else None


def rank(designs: list[RankInput]) -> dict[str, list[Objective]]:
    """candidate_id -> objectives it wins (a design may win several, or none)."""
    passing = [d for d in designs if d.verdict == "pass"]
    pool = passing or [d for d in designs if d.verdict == "review"]
    wins: dict[str, list[Objective]] = {d.candidate_id: [] for d in designs}

    priced = [d for d in pool if d.price_usd is not None]
    if priced:
        best = min(priced, key=lambda d: (d.price_usd, d.candidate_id))
        wins[best.candidate_id].append(Objective.cost)

    with_margin = [d for d in pool if _torque_margin(d) is not None]
    if with_margin:
        best = max(with_margin, key=lambda d: (_torque_margin(d), d.candidate_id))
        wins[best.candidate_id].append(Objective.performance)

    us = [d for d in pool if d.origin_tier in ("T1", "T2")]
    if us:
        inf = float("inf")
        best = min(
            us,
            key=lambda d: (_TIER_ORDER[d.origin_tier], d.price_usd or inf, d.candidate_id),
        )
        wins[best.candidate_id].append(Objective.us_first)
    return wins
