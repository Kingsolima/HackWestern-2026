"""Tournament (ARCHITECTURE §3 #8): best passing candidate per objective. Deterministic.

Owner 3: implement. Input = verified candidates with CheckResult verdict == pass;
output = one DesignVariant per Objective (cost, performance, us_first).
"""

from app.schemas import CheckResult, DesignVariant, MotorCandidate


def run_tournament(candidates: list[tuple[MotorCandidate, CheckResult]]) -> list[DesignVariant]:
    raise NotImplementedError
