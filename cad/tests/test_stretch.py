"""Stretch block model with the regenerated shoulder mount."""

import json
import struct

import pytest
from fastapi.testclient import TestClient

from cad_worker import server
from cad_worker.export import export
from cad_worker.robot import HIGHLIGHT_COLOR
from cad_worker.stretch import GEARBOX_LEN, PLATE_T, StretchParams, measure_stretch, stretch


def glb_nodes(path) -> dict[str, dict]:
    glb = path.read_bytes()
    doc = json.loads(glb[20 : 20 + struct.unpack_from("<I", glb, 12)[0]])
    return {n["name"]: n for n in doc["nodes"] if "name" in n}


def checks(fit: dict) -> dict[str, dict]:
    return {c["name"]: c for c in fit["fit_checks"]}


def test_baseline_shoulder_fits_without_a_sleeve():
    fit = measure_stretch(StretchParams())
    c = checks(fit)
    assert fit["robot"] == "stretch" and fit["illustrative"] is True
    assert c["shoulder_envelope"]["value"] == GEARBOX_LEN + PLATE_T + 120.0
    assert c["shoulder_envelope"]["ok"] and c["shaft_to_gearbox_bore"]["ok"]
    assert not fit["needs_bore_sleeve"]


def test_long_motor_breaks_the_envelope_and_fat_shaft_the_bore():
    c = checks(measure_stretch(StretchParams(body_len=200.0, shaft_d=19.05)))
    assert not c["shoulder_envelope"]["ok"] and not c["shaft_to_gearbox_bore"]["ok"]
    assert measure_stretch(StretchParams(shaft_d=12.7))["needs_bore_sleeve"]


def test_stretch_glb_has_named_parts_and_highlighted_mount(tmp_path):
    p = StretchParams(shaft_d=12.7, highlight=True)
    nodes = glb_nodes(export(stretch(p), tmp_path, "s")["glb"])
    assert {"mount_plate", "shoulder_motor", "shoulder_gearbox", "mast", "arm", "bore_sleeve"} <= (
        nodes.keys()
    )
    assy = stretch(p)
    plate = assy.children[[c.name for c in assy.children].index("mount_plate")]
    assert plate.color.toTuple()[:3] == pytest.approx(HIGHLIGHT_COLOR.toTuple()[:3])


def test_build_route_builds_stretch_with_its_own_baseline_length(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "OUT_DIR", tmp_path)
    c = TestClient(server.app)
    r = c.post("/build", json={"design_id": "s1", "robot": "stretch", "frame": "34"})
    assert r.status_code == 200
    assert r.json()["fit"]["params"]["body_len"] == 120.0
    assert c.get("/designs/s1/glb").content[:4] == b"glTF"
    r = c.post(
        "/build", json={"design_id": "s2", "robot": "stretch", "frame": "34", "body_len": 150}
    )
    assert r.json()["fit"]["params"]["body_len"] == 150
    # the other robots keep their 56 mm default
    assert c.post("/build", json={"design_id": "w1"}).json()["fit"]["params"]["body_len"] == 56.0
