"""Datasheet reader (ARCHITECTURE §3 #5). Owner 2.

Gemini multimodal: PDF / spec-table image → strict JSON matching MotorCandidate.
Only frame, body length and ratings come from here; never bolt patterns.
"""

from app.schemas import MotorCandidate


async def read_datasheet(url: str) -> MotorCandidate:
    raise NotImplementedError
