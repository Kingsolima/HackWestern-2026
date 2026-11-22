#!/usr/bin/env python3
"""End-to-end check of a running site: `python3 scripts/smoke.py http://localhost:8080`.

Health, database, CAD worker, then one replay job per demo path (wheeled demo, AR4 club,
Stretch, and an onboarded company built from the example answers). Replay jobs make no paid
calls. Exits 1 unless every job ends DONE with the events its screens need. Standard library
only, so it runs anywhere.

To record what a replay is missing, run it once with SMOKE_MODE=mixed and LIVE_JOBS_TOKEN set:
recorded calls replay, the rest run for real (this spends TinyFish and Gemini credit) and are
saved to data/recordings on the machine running the backend. SMOKE_ONLY=wheeled limits the jobs
to those whose name contains the word.
"""

import json
import os
import sys
import urllib.error
import urllib.request
from collections import Counter

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080").rstrip("/")
MODE = os.environ.get("SMOKE_MODE", "replay")
TOKEN = os.environ.get("LIVE_JOBS_TOKEN", "")
ONLY = os.environ.get("SMOKE_ONLY", "")  # run only the jobs whose name contains this
failures: list[str] = []


def call(path: str, body: dict | None = None, timeout: float = 60) -> tuple[int, bytes]:
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if MODE != "replay" and TOKEN:
        headers["X-Live-Token"] = TOKEN
    request = urllib.request.Request(BASE + path, data=data, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def report(name: str, ok: bool, detail: str = "") -> None:
    print(f"{'ok  ' if ok else 'FAIL'} {name}{': ' + detail if detail else ''}")
    if not ok:
        failures.append(name)


def get_json(name: str, path: str, body: dict | None = None):
    status, raw = call(path, body)
    if status >= 300:
        report(name, False, f"HTTP {status} {raw[:200].decode(errors='replace')}")
        return None
    return json.loads(raw)


def run_job(name: str, body: dict, need: tuple[str, ...]) -> None:
    """Start a job, follow its event stream to the end, and check what it sent."""
    if ONLY and ONLY not in name:
        return
    job = get_json(name, "/api/jobs", {"mode": MODE, **body})
    if job is None:
        return
    events = []
    with urllib.request.urlopen(f"{BASE}/api/jobs/{job['job_id']}/events", timeout=1800) as stream:
        for line in stream:
            if line.startswith(b"data:"):
                events.append(json.loads(line[5:]))
    kinds = Counter(e["type"] for e in events)
    final = events[-1]["data"].get("stage") if events else None
    errors = [e["data"]["message"] for e in events if e["type"] == "error"]
    missing = [k for k in need if not kinds[k]]
    seen = ", ".join(f"{kinds[k]} {k}" for k in need)
    problems = [f"ended {final}"] * (final != "DONE") + [f"no {k}" for k in missing] + errors
    report(name, not problems, "; ".join(problems) if problems else seen)


def main() -> int:
    print(f"Checking {BASE} ({MODE} jobs)")
    status, raw = call("/health")
    report("backend /health", status == 200, raw[:100].decode(errors="replace"))
    status, raw = call("/health/db")
    report("database /health/db", status == 200, raw[:200].decode(errors="replace"))
    status, raw = call("/")
    report("website /", status == 200 and b'<div id="root"' in raw)
    for starter in ("starter", "starter_ar4", "starter_stretch"):
        status, raw = call(f"/cad/designs/{starter}/glb")
        report(f"CAD model {starter}", status == 200 and raw[:4] == b"glTF")
    projects = get_json("projects list", "/api/projects") or []
    report("projects list", {"ar4_club", "stretch"} <= {p["id"] for p in projects})

    motor_search = ("claim_verified", "check_result", "design_ready")
    risk_map = ("project", "risk_line", "alternative", "recommendation")
    run_job("wheeled demo job", {}, ("compliance", *motor_search))
    run_job("AR4 club job", {"project_id": "ar4_club"}, (*risk_map, *motor_search))
    run_job("Stretch job", {"project_id": "stretch"}, (*risk_map, *motor_search))

    # Onboarding: the example answers are read from a recording, then run as the user's project.
    robot = get_json("demo robot", "/api/robot")
    answers = get_json("example answers", "/api/intake/example")
    if robot and answers:
        intake_body = {"robot_kind": "wheeled", "bom": robot["bom"], "cad": None}
        intake = get_json("onboarding intake", "/api/intake", {**intake_body, "answers": answers})
        if intake:
            report("onboarding intake", bool(intake["company"]), f"{len(intake['company'])} facts")
            for spec in intake["specs"]:
                if spec["robot_field"] in robot["requirements"]:
                    robot["requirements"][spec["robot_field"]] = spec["value"] / spec["divisor"]
            run_job(
                "onboarded company job",
                {"robot": robot, "company": intake["company"]},
                (*risk_map, *motor_search),
            )

    print("FAILED: " + ", ".join(failures) if failures else "All checks passed.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
