"""Run the TinyAgent motor extraction on the Teknic ClearPath-SD page.

    uv run python scripts/teknic_probe.py                  # replay the recorded run (no network)
    uv run python scripts/teknic_probe.py --live           # one real TinyAgent run, records it
    uv run python scripts/teknic_probe.py --resume RUN_ID [--seen-log probe.log]
        # the live stream dropped: fetch the run's result instead of paying for a new run,
        # and record it (with the progress lines from the earlier probe output, if given)

A live run costs TinyFish agent credit. Open the printed streaming URL to watch it.
"""

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pydantic import ValidationError  # noqa: E402

from app.agents.motor_schema import TfMotorCandidate, output_schema  # noqa: E402
from app.agents.teknic import TEKNIC_URL, build_goal  # noqa: E402
from app.tfclient.client import TinyFishClient  # noqa: E402

TERMINAL = ("COMPLETED", "FAILED", "CANCELLED")


def report(complete: dict[str, Any]) -> int:
    print(f"\nrun status: {complete.get('status')}  (COMPLETED does not mean success)")
    if complete.get("error"):
        print(f"error: {complete['error']}")
    result = complete.get("result")
    if not isinstance(result, dict):
        print(f"no structured result: {result!r}")
        return 1
    try:
        cand = TfMotorCandidate.model_validate(result)
    except ValidationError as e:
        print(f"result does not match the schema:\n{e}\nraw: {result}")
        return 1

    print(f"agent status: {cand.status} — {cand.reason}")
    print(f"{cand.manufacturer} {cand.part_number} | {cand.motor_type} | NEMA {cand.nema_frame}")
    print(f"product: {cand.product_url}\ndatasheet: {cand.datasheet_url}\n")
    for s in cand.specs:
        at = f" @ {s.at_speed_value} {s.at_speed_unit}" if s.at_speed_value is not None else ""
        print(f"  {s.name:<20} {s.value:>10g} {s.unit}{at}")
        print(f"  {'':<20} quote: {s.quote!r}")
        print(f"  {'':<20} from:  {s.source_url}")
    print(f"\norigin: {cand.country_of_origin}\n  quote: {cand.origin_quote!r}")
    print(f"  from:  {cand.origin_source_url}")
    return 0 if cand.status in ("success", "incomplete") else 1


async def run(live: bool, max_duration: int) -> int:
    client = TinyFishClient("live" if live else "replay")
    print(f"mode: {client.mode} | url: {TEKNIC_URL}")
    complete = None
    async for ev in client.agent_run_sse(
        TEKNIC_URL, build_goal(), output_schema(), max_duration_seconds=max_duration
    ):
        t = ev.get("type")
        if t == "STARTED":
            print(f"run started: {ev.get('run_id')}")
        elif t == "STREAMING_URL":
            print(f"watch live: {ev.get('streaming_url')}")
        elif t == "PROGRESS":
            print(f"  · {ev.get('purpose')}")
        elif t == "COMPLETE":
            complete = ev
        sys.stdout.flush()
    if complete is None:
        print("stream ended without COMPLETE; recover with --resume <run_id>")
        return 1
    return report(complete)


def events_from_log(path: Path, run_id: str) -> list[dict[str, Any]]:
    """Rebuild STARTED/STREAMING_URL/PROGRESS events from this script's own earlier output."""
    events: list[dict[str, Any]] = [{"type": "STARTED", "run_id": run_id}]
    for line in path.read_text().splitlines():
        if line.startswith("watch live: "):
            url = line.removeprefix("watch live: ")
            events.append({"type": "STREAMING_URL", "run_id": run_id, "streaming_url": url})
        elif line.startswith("  · "):
            purpose = line.removeprefix("  · ")
            events.append({"type": "PROGRESS", "run_id": run_id, "purpose": purpose})
    return events


async def resume(run_id: str, max_duration: int, seen_log: Path | None) -> int:
    client = TinyFishClient("live")
    r = await client.get_run(run_id)
    print(f"run {run_id}: {r.get('status')}")
    if r.get("status") not in TERMINAL:
        print("not finished yet; try again shortly (do not start a new run)")
        return 1
    request = client.agent_request(TEKNIC_URL, build_goal(), output_schema(), max_duration, "lite")
    seen = (
        events_from_log(seen_log, run_id) if seen_log else [{"type": "STARTED", "run_id": run_id}]
    )
    client.record_recovered_run(request, r, seen)
    print(f"recorded fixture: {client.recorder.path('agent', request).name}")
    return report({"status": r.get("status"), "result": r.get("result"), "error": r.get("error")})


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="real TinyAgent run (costs credit)")
    ap.add_argument("--resume", metavar="RUN_ID", help="recover a run whose stream dropped")
    ap.add_argument("--seen-log", type=Path, help="earlier probe output, for --resume")
    ap.add_argument("--max-duration", type=int, default=240)
    a = ap.parse_args()
    if a.resume:
        sys.exit(asyncio.run(resume(a.resume, a.max_duration, a.seen_log)))
    sys.exit(asyncio.run(run(a.live, a.max_duration)))
