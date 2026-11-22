"""Run inside the CAD image: make test-cad."""

import json
import math
import struct

import pytest
from cad_worker import server
from cad_worker.export import export
from cad_worker.robot import RobotParams, measure, robot
from fastapi.testclient import TestClient

TEKNIC = dict(frame="23", body_len=84.84, shaft_d=9.52)  # CPM-SDSK-2310D-RLN page values


def test_ground_clearance_follows_05_formula():
    # r - flange/2 - clearance - bracket_t - deck_t
    assert measure(RobotParams(frame="17"))["ground_clearance_mm"] == pytest.approx(22.85)
    assert measure(RobotParams(frame="23"))["ground_clearance_mm"] == pytest.approx(15.4)
    m34 = measure(RobotParams(frame="34", body_len=80))
    assert m34["ground_clearance_mm"] == pytest.approx(1.0)
    assert not m34["fit_ground"]


def test_teknic_needs_hub_adapter_but_fits_envelope():
    m = measure(RobotParams(**TEKNIC))
    assert m["needs_hub_adapter"] and m["fit_envelope"] and m["fit_ground"]
    assert not measure(RobotParams(frame="23"))["needs_hub_adapter"]  # baseline 6.35 shaft


def _bbox(assy, name):
    child = assy.objects[name]
    return child.obj.val().moved(child.loc).BoundingBox()


@pytest.mark.parametrize(
    "kw", [dict(frame="17", body_len=40), dict(frame="23"), dict(frame="34", body_len=80), TEKNIC]
)
def test_robot_sits_on_wheels_and_shafts_hit_hubs(kw):
    p = RobotParams(**kw)
    assy = robot(p)
    assert assy.toCompound().BoundingBox().zmin == pytest.approx(0, abs=0.01)
    for side in ("left", "right"):
        s, w = _bbox(assy, f"shaft_{side}"), _bbox(assy, f"wheel_{side}")
        assert (s.zmin + s.zmax) / 2 == pytest.approx(p.wheel_r)
        assert w.zmin == pytest.approx(0, abs=0.01)
        wheel_mid_y = (w.ymin + w.ymax) / 2
        assert math.isclose(abs(s.ymax if wheel_mid_y > 0 else s.ymin), abs(wheel_mid_y))
    adapters = {"hub_adapter_left", "hub_adapter_right"} <= set(assy.objects)
    assert adapters == measure(p)["needs_hub_adapter"]


def test_glb_keeps_part_names(tmp_path):
    glb = export(robot(RobotParams(**TEKNIC)), tmp_path, "t")["glb"].read_bytes()
    json_len = struct.unpack_from("<I", glb, 12)[0]
    nodes = {n.get("name") for n in json.loads(glb[20 : 20 + json_len])["nodes"]}
    assert {"bracket_left", "motor_right", "hub_adapter_left"} <= nodes


def test_server_build_and_design_routes(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "OUT_DIR", tmp_path)
    c = TestClient(server.app)
    r = c.post("/build", json={"design_id": "teknic_a", **TEKNIC})
    assert r.status_code == 200 and r.json()["fit"]["needs_hub_adapter"]
    assert c.get("/designs/teknic_a/glb").content[:4] == b"glTF"
    assert c.get("/designs/teknic_a/step").status_code == 200
    assert c.get("/designs/teknic_a/fit").json()["ground_clearance_mm"] == pytest.approx(15.4)
    assert c.get("/designs/missing/glb").status_code == 404
    assert c.post("/build", json={"design_id": "../x"}).status_code == 422


def test_starter_robot_is_built_at_startup(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "OUT_DIR", tmp_path)
    with TestClient(server.app) as c:  # entering runs the startup build
        assert c.get("/designs/starter/glb").content[:4] == b"glTF"
        assert c.get("/designs/starter/fit").json()["params"]["frame"] == "17"
        assert c.get("/designs/starter_ar4/fit").json()["robot"] == "ar4"


def test_fit_exposes_bracket_thickness_and_clearance_for_the_checks():
    m = measure(RobotParams(frame="23", clearance=7.0))
    assert m["bracket"]["thickness_mm"] == 5.0
    assert m["clearance_mm"] == 7.0
    # envelope uses the same numbers the checks will read
    assert m["envelope_used_mm"] == 56.0 + m["bracket"]["thickness_mm"] + m["clearance_mm"]


def test_highlight_colours_only_the_brackets():
    plain = robot(RobotParams(frame="23"))
    lit = robot(RobotParams(frame="23", highlight=True))
    for side in ("left", "right"):
        assert (
            lit.objects[f"bracket_{side}"].color.toTuple()
            != plain.objects[f"bracket_{side}"].color.toTuple()
        )
        assert (
            lit.objects[f"motor_{side}"].color.toTuple()
            == plain.objects[f"motor_{side}"].color.toTuple()
        )
