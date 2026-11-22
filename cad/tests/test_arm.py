"""AR4 arm with the regenerated J2 mount (BUILD-PLAN-v4 §7)."""

import json
import struct

import pytest
from fastapi.testclient import TestClient

from cad_worker import server
from cad_worker.arm import GEARBOX_LEN, PLATE_T, ArmParams, arm, measure_arm
from cad_worker.export import export
from cad_worker.robot import HIGHLIGHT_COLOR, RobotParams, measure


def glb_nodes(path) -> dict[str, dict]:
    glb = path.read_bytes()
    doc = json.loads(glb[20 : 20 + struct.unpack_from("<I", glb, 12)[0]])
    return {n["name"]: n for n in doc["nodes"] if "name" in n}


def checks(fit: dict) -> dict[str, dict]:
    return {c["name"]: c for c in fit["fit_checks"]}


def test_baseline_j2_fits():
    fit = measure_arm(ArmParams())
    c = checks(fit)
    assert c["j2_envelope"]["value"] == GEARBOX_LEN + PLATE_T + 56.0
    assert c["j2_envelope"]["ok"] and c["shaft_to_gearbox_bore"]["ok"]
    assert not fit["needs_bore_sleeve"]
    assert all({"name", "value", "limit", "unit", "ok"} <= row.keys() for row in fit["fit_checks"])


def test_long_motor_breaks_the_envelope_and_fat_shaft_the_bore():
    c = checks(measure_arm(ArmParams(frame="34", body_len=120.0, shaft_d=9.52)))
    assert not c["j2_envelope"]["ok"]
    assert not c["shaft_to_gearbox_bore"]["ok"]


def test_smaller_shaft_gets_a_sleeve():
    fit = measure_arm(ArmParams(frame="17", shaft_d=5.0))
    assert checks(fit)["shaft_to_gearbox_bore"]["ok"] and fit["needs_bore_sleeve"]


def test_pilot_and_bolt_spacing_override_the_nema_table():
    mount = measure_arm(ArmParams(frame="23", pilot_d=40.0, bolt_spacing=50.0))["mount"]
    assert mount["pilot_hole_mm"] == 41.0 and mount["bolt_spacing_mm"] == 50.0
    bracket = measure(RobotParams(frame="23", pilot_d=40.0, bolt_spacing=50.0))["bracket"]
    assert bracket["pilot_hole_mm"] == 41.0 and bracket["bolt_spacing_mm"] == 50.0


def test_arm_glb_has_named_parts_and_highlighted_mount(tmp_path):
    p = ArmParams(frame="17", shaft_d=5.0, highlight=True)
    paths = export(arm(p), tmp_path, "a")
    nodes = glb_nodes(paths["glb"])
    assert {"mount_plate", "j2_motor", "j2_gearbox", "upper_arm", "bore_sleeve"} <= nodes.keys()
    assy = arm(p)
    assert assy.children[[c.name for c in assy.children].index("mount_plate")].color.toTuple()[
        :3
    ] == pytest.approx(HIGHLIGHT_COLOR.toTuple()[:3])


def test_wheeled_fit_has_generic_rows_too():
    fit = measure(RobotParams())
    assert fit["robot"] == "wheeled"
    assert set(checks(fit)) == {"ground_clearance", "inboard_envelope"}


def test_build_route_takes_robot(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "OUT_DIR", tmp_path)
    c = TestClient(server.app)
    r = c.post("/build", json={"design_id": "arm1", "robot": "ar4", "frame": "23", "shaft_d": 9.52})
    assert r.status_code == 200
    assert r.json()["fit"]["robot"] == "ar4"
    assert not checks(r.json()["fit"])["shaft_to_gearbox_bore"]["ok"]
    assert c.get("/designs/arm1/glb").content[:4] == b"glTF"
    # no robot field: wheeled, as before
    assert c.post("/build", json={"design_id": "w1"}).json()["fit"]["robot"] == "wheeled"
    assert c.post("/build", json={"design_id": "x", "robot": "tank"}).status_code == 422
