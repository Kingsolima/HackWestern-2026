"""Run view: the last recorded page snapshot of an agent run, for the replay bays."""

from app.api.runs import last_snapshot, with_base
from app.tfclient.recorder import Recorder


def record(rec: Recorder, request: dict, response: dict) -> None:
    rec._save("agent", request, {"response": response})


def test_last_snapshot_takes_the_latest_step_with_html(tmp_path):
    rec = Recorder(tmp_path, "replay")
    record(
        rec,
        {"op": "run_steps", "run_id": "r1"},
        {
            "steps": [
                {"id": "s1", "action": "a"},
                {"id": "s2", "action": "b"},
                {"id": "s3", "action": "c"},
            ]
        },
    )
    record(rec, {"op": "step_html", "run_id": "r1", "step_id": "s1"}, {"html": "<p>first</p>"})
    record(rec, {"op": "step_html", "run_id": "r1", "step_id": "s2"}, {"html": "<p>second</p>"})
    record(
        rec,
        {"op": "step_canonical", "run_id": "r1", "step_id": "s2"},
        {"canonical": "https://teknic.com/x"},
    )
    # s3 has no snapshot recorded (TinyFish 404s on a run's final step)
    assert last_snapshot(rec, "r1") == ("<p>second</p>", "https://teknic.com/x")
    assert last_snapshot(rec, "unknown") is None


def test_with_base_resolves_relative_links_against_the_captured_page():
    assert with_base("<html><head><title>t</title></head></html>", "https://a.com/p") == (
        '<html><head><base href="https://a.com/p"><title>t</title></head></html>'
    )
    assert with_base("<p>x</p>", "https://a.com/") == '<base href="https://a.com/"><p>x</p>'
    assert with_base("<p>x</p>", None) == "<p>x</p>"
    assert with_base("<p>x</p>", "javascript:alert(1)") == "<p>x</p>"
