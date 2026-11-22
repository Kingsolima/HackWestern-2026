"""What an agent's browser showed: the last page snapshot recorded for a TinyFish run, so a
replayed run's bay can show the page and not only its step log."""

import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse

from app.api.jobs import get_runtime
from app.orchestrator.runtime import Runtime
from app.tfclient.recorder import Recorder

router = APIRouter(prefix="/api/runs")

RUN_ID = re.compile(r"^[A-Za-z0-9-]{1,64}$")
# The snapshot is third-party HTML: never run its scripts, and only this app may frame it.
CSP = "script-src 'none'; object-src 'none'; frame-ancestors 'self'"


def last_snapshot(recorder: Recorder, run_id: str) -> tuple[str, str | None] | None:
    """(html, canonical url) of the latest step with a recorded snapshot, or None."""
    steps = recorder.recorded("agent", {"op": "run_steps", "run_id": run_id})
    for step in reversed((steps or {}).get("steps", [])):
        ref = {"run_id": run_id, "step_id": step["id"]}
        html = (recorder.recorded("agent", {"op": "step_html"} | ref) or {}).get("html")
        if html:
            canonical = (recorder.recorded("agent", {"op": "step_canonical"} | ref) or {}).get(
                "canonical"
            )
            return html, canonical
    return None


def with_base(html: str, url: str | None) -> str:
    """Resolve the page's relative links and styles against where it was captured."""
    if not url or not url.startswith(("http://", "https://")):
        return html
    tag = f'<base href="{url.replace(chr(34), "%22")}">'
    head = re.search(r"<head[^>]*>", html, re.IGNORECASE)
    return html[: head.end()] + tag + html[head.end() :] if head else tag + html


@router.get("/{run_id}/view", response_class=HTMLResponse)
def get_run_view(run_id: str, runtime: Annotated[Runtime, Depends(get_runtime)]) -> HTMLResponse:
    if not RUN_ID.match(run_id):
        raise HTTPException(status_code=404, detail="no such run")
    found = last_snapshot(Recorder(runtime.settings.recordings_dir, "replay"), run_id)
    if found is None:
        raise HTTPException(status_code=404, detail=f"no page snapshot recorded for run {run_id}")
    return HTMLResponse(with_base(*found), headers={"Content-Security-Policy": CSP})
