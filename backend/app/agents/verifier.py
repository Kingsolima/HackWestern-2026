"""Verifier (ARCHITECTURE §3 #6). Deterministic. Owner 2.

Re-fetch product_url html via TinyFetch, string-match origin_quote, price and NEMA frame,
store the html in Object Storage as evidence. Only `verified` reaches the checks.
"""

from app.schemas import MotorCandidate, VerifierStatus


async def verify(candidate: MotorCandidate) -> VerifierStatus:
    raise NotImplementedError
