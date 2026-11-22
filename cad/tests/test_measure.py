"""POST /measure on the worker's own exports: what onboarding reads from an uploaded STEP."""

import cadquery as cq
import pytest
from fastapi.testclient import TestClient

from cad_worker.export import export
from cad_worker.measure import measure_step
from cad_worker.robot import RobotParams, robot
from cad_worker.server import app


@pytest.fixture(scope="module")
def starter_step(tmp_path_factory):
    return export(robot(RobotParams()), tmp_path_factory.mktemp("step"), "starter")["step"]


def test_measures_named_parts_of_the_starter_robot(starter_step):
    m = measure_step(starter_step)
    parts = {p["name"]: p for p in m["parts"]}
    assert {"wheel_left", "wheel_right", "motor_left", "motor_right", "caster"} <= set(parts)
    # 60 mm wheel radius: the wheel's largest side is its diameter.
    assert max(parts["wheel_left"]["bbox_mm"]) == pytest.approx(120.0, abs=0.01)
    assert m["bbox_mm"][0] == pytest.approx(300.0, abs=0.5)
    assert m["volume_mm3"] == pytest.approx(sum(p["volume_mm3"] for p in m["parts"]), rel=1e-3)


def test_a_step_without_assembly_names_gives_unnamed_solids(tmp_path):
    path = tmp_path / "box.step"
    cq.exporters.export(cq.Workplane().box(10, 20, 30), str(path))
    m = measure_step(path)
    assert [p["name"] for p in m["parts"]] == [""]
    assert sorted(m["bbox_mm"]) == pytest.approx([10, 20, 30], abs=0.01)
    assert m["volume_mm3"] == pytest.approx(6000, rel=1e-3)


def test_endpoint_takes_the_file_as_the_body_and_rejects_junk(starter_step):
    with TestClient(app) as client:
        ok = client.post("/measure", content=starter_step.read_bytes())
        assert ok.status_code == 200 and len(ok.json()["parts"]) == 11
        assert client.post("/measure", content=b"").status_code == 400
        assert client.post("/measure", content=b"this is not a STEP file").status_code == 422
