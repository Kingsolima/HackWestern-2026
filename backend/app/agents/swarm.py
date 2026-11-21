"""TinyFish agent swarm (ARCHITECTURE §3 #3–4). Owner 2.

- Discovery: TinySearch + TinyFetch (cheap, broad).
- Extraction: TinyAgent via /run-batch or /run-sse with MotorCandidate as output_schema;
  surface each run's streaming_url to the frontend as a live tile.
- Use max_duration_seconds (GA) as the run limit. CAPTCHA → status=blocked, move on.
- Log every run to Tiger Data `agent_runs`.
- Seed with data/seed_motors.json so the demo can't come up empty.
"""

from app.schemas import MotorCandidate, RobotRequirements


async def find_candidates(req: RobotRequirements) -> list[MotorCandidate]:
    raise NotImplementedError
