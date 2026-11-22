"""Run one job outside the API and print its events; live mode records every call.

Run from backend/: uv run python -m scripts.run_job --mode live
"""

import argparse
import asyncio
import json

import httpx

from app.api.routes import load_demo_robot
from app.config import settings
from app.orchestrator.runtime import Runtime


def summary(event_type: str, data: dict) -> str:
    match event_type:
        case "stage":
            return data["stage"]
        case "claim_verified" | "claim_rejected":
            claim = data["claim"]
            line = f"{claim['field']} = {claim['raw_value']} {claim['raw_unit'] or ''}"
            return f"{line} | quote: {claim['quote']!r} | {data.get('reason', 'verified')}"
        case _:
            return json.dumps(data)[:200]


async def main(mode: str) -> None:
    async with httpx.AsyncClient(timeout=60.0) as http:
        runtime = Runtime(settings, http)
        job = runtime.start_job(load_demo_robot(), mode)
        async for event in job.ctx.log.subscribe():
            print(f"{event.id:3} {event.type:18} {summary(event.type, event.data)}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["live", "replay", "mixed"], default="replay")
    asyncio.run(main(parser.parse_args().mode))
