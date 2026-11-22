import math

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.intake import load_example
from app.api.routes import load_demo_robot
from app.cad_client import CadClient
from app.config import Settings, settings
from app.intake.extract import confirm, convert, prompt, response_schema
from app.intake.from_bom import specs_from_bom
from app.intake.from_cad import specs_from_cad
from app.intake.merge import merge
from app.intake.schema import WHEELED, Answers, CadMeasure, CadPart, Found
from app.main import app
from app.schemas import BomRow, RobotRequirements
from app.tfclient.gemini import GeminiClient
from app.tfclient.recorder import Recorder, ReplayMiss


def row(part, category, qty=1):
    return BomRow(part=part, category=category, qty=qty, unit_cost_usd="1", origin="US")


def values(found):
    return {f.field: f.value for f in found}


def test_every_wheeled_spec_fills_one_robot_requirement():
    assert sorted(f.robot_field for f in WHEELED) == sorted(RobotRequirements.model_fields)


def test_bom_rules_read_the_demo_bom():
    found = specs_from_bom(load_demo_robot().bom)
    assert values(found) == {"n_drive_motors": 2, "bus_voltage_v": 24}
    assert {f.field: f.evidence for f in found} == {
        "n_drive_motors": "2 x Drive motor (NEMA 23)",
        "bus_voltage_v": "1 x 24V battery pack",
    }


def test_bom_rules_read_gear_ratio_and_wheel_size():
    found = specs_from_bom(
        [
            row("Planetary gearbox 50:1", "gearbox"),
            row("Wheel 120 mm dia", "frame", 2),
            row("Wheel encoder 40 mm dia", "encoder", 2),
            row("48 VDC power supply", "electronics"),
            row("Motor driver 24V", "electronics"),
        ]
    )
    assert values(found) == {"gear_ratio": 50, "wheel_radius_mm": 60, "bus_voltage_v": 48}


def cad(parts):
    return CadMeasure(
        parts=[CadPart(name=n, bbox_mm=b, volume_mm3=1000) for n, b in parts],
        bbox_mm=(300, 220, 130),
        volume_mm3=2_000_000,
    )


def test_cad_rules_read_wheels_motors_and_an_estimated_mass():
    found = specs_from_cad(
        cad(
            [
                ("wheel_left", (120.004, 25, 119.998)),
                ("wheel_right", (120.0, 25, 120.0)),
                ("caster", (30, 30, 30)),
                ("hub_adapter_left", (20, 12, 20)),
                ("motor_left", (57, 56, 57)),
                ("motor_right", (57, 56, 57)),
                ("bracket_left", (70, 5, 70)),
            ]
        )
    )
    assert values(found) == {"wheel_radius_mm": 60.0, "n_drive_motors": 2, "mass_kg": 5.4}
    assert "estimate" in next(f for f in found if f.field == "mass_kg").evidence


def test_cad_without_named_parts_only_estimates_mass():
    assert list(values(specs_from_cad(cad([("", (10, 10, 10))])))) == ["mass_kg"]


ANSWERS = Answers(
    who="We are Acme Robotics. We build ToteBot, which moves totes in warehouses.",
    market="We sell to the US Army and to retailers. Built in Ohio, runs in the US and Canada.",
    limits="Budget is $1,200 per robot and we need parts in 6 weeks. No Chinese magnets.",
    drivetrain="It weighs 44 lb with payload, tops out at 4 mph on 6 inch diameter wheels "
    "and climbs a 10% grade.",
)


def number(field, value, unit, quote):
    return {"field": field, "value": value, "unit": unit, "quote": quote}


def fact(field, value, quote):
    return {"field": field, "value": value, "quote": quote}


def test_confirm_keeps_quoted_values_and_converts_units():
    raw = {
        "facts": [
            fact("company_name", "Acme Robotics", "We are Acme Robotics"),
            fact("sells_to_us_federal", "Yes", "We sell to the US Army"),
            fact("deploy_countries", "us, ca", "runs in the US and Canada"),
            fact("final_assembly_country", "US", "Built in Ohio"),
        ],
        "numbers": [
            number("mass_kg", 44, "lb", "weighs 44 lb with payload"),
            number("v_max_mps", 4, "mph", "tops out at 4 mph"),
            number("wheel_diameter_mm", 6, "inch", "6 inch diameter wheels"),
            number("max_slope_deg", 10, "%", "climbs a 10% grade"),
            number("budget_usd", 1200, "$", "Budget is $1,200 per robot"),
            number("need_by_days", 6, "weeks", "need parts in 6 weeks"),
        ],
    }
    company, specs, dropped = confirm(raw, ANSWERS, WHEELED)
    assert dropped == []
    got = values(specs)
    assert got["mass_kg"] == pytest.approx(19.9581, abs=1e-4)
    assert got["v_max_mps"] == pytest.approx(1.7882, abs=1e-4)
    assert got["wheel_radius_mm"] == 76.2
    assert got["max_slope_deg"] == pytest.approx(math.degrees(math.atan(0.1)), abs=1e-4)
    assert all(f.source == "answer" for f in specs)
    assert {c.field: c.value for c in company} == {
        "company_name": "Acme Robotics",
        "sells_to_us_federal": "yes",
        "deploy_countries": "US, CA",
        "final_assembly_country": "US",
        "budget_usd": "$1,200",
        "need_by_days": "42 days",
    }


def test_confirm_drops_what_the_text_does_not_back():
    raw = {
        "facts": [
            fact("company_name", "Globex", "We are Globex"),  # quote not in the answers
            fact("kind", "startup", "We are Acme Robotics"),  # not an allowed value
            fact("final_assembly_country", "Ohio", "Built in Ohio"),  # not a country code
        ],
        "numbers": [
            number("mass_kg", 20, "kg", "weighs 44 lb with payload"),  # number not in the quote
            number("accel_mps2", 2, "m/s²", "accelerates at 2 m/s²"),  # quote not in the answers
            number("v_max_mps", 4, "knots", "tops out at 4 mph"),  # unit we do not convert
            number("max_slope_deg", 1200, "deg", "$1,200 per robot"),  # out of range
            number("n_drive_motors", 4, "", "tops out at 4 mph"),  # kept: stated number, no unit
            number("gear_ratio", "many", "", "moves totes"),  # not a number
            number("made_up_field", 4, "", "tops out at 4 mph"),
        ],
    }
    company, specs, dropped = confirm(raw, ANSWERS, WHEELED)
    assert company == []
    assert values(specs) == {"n_drive_motors": 4}
    assert sorted(d.split(":")[0] for d in dropped) == [
        "accel_mps2", "company_name", "final_assembly_country", "kind", "mass_kg",
        "max_slope_deg", "v_max_mps",
    ]  # fmt: skip


def test_confirm_accepts_a_number_the_user_wrote_as_a_word():
    answers = Answers(drivetrain="It has four drive motors and we need parts in six weeks.")
    raw = {
        "facts": [],
        "numbers": [
            number("n_drive_motors", 4, "", "four drive motors"),
            number("need_by_days", 6, "weeks", "six weeks"),
            number("mass_kg", 5, "kg", "four drive motors"),  # the quote says four, not five
        ],
    }
    company, specs, dropped = confirm(raw, answers, WHEELED)
    assert values(specs) == {"n_drive_motors": 4}
    assert [c.value for c in company] == ["42 days"]
    assert [d.split(":")[0] for d in dropped] == ["mass_kg"]


def test_confirm_keeps_the_first_of_a_repeated_field():
    raw = {
        "facts": [],
        "numbers": [
            number("mass_kg", 44, "lb", "weighs 44 lb"),
            number("mass_kg", 4, "kg", "4 mph"),
        ],
    }
    assert len(confirm(raw, ANSWERS, WHEELED)[1]) == 1


def test_convert():
    assert convert(2, " M/S ", "speed") == 2
    assert convert(90, "%", "fraction") == pytest.approx(0.9)
    assert convert(3, "anything", "plain") == 3
    assert convert(3, "furlongs", "length") is None


def test_stray_whitespace_around_an_answer_does_not_change_the_prompt():
    padded = Answers(who=f"  {ANSWERS.who}\n", market=ANSWERS.market, limits=ANSWERS.limits)
    plain = Answers(who=ANSWERS.who, market=ANSWERS.market, limits=ANSWERS.limits)
    assert prompt(padded, WHEELED) == prompt(plain, WHEELED)


def test_prompt_and_schema_name_every_field():
    text, schema = prompt(ANSWERS, WHEELED), response_schema(WHEELED)
    names = schema["properties"]["numbers"]["items"]["properties"]["field"]["enum"]
    assert set(names) >= {f.id for f in WHEELED} | {"wheel_diameter_mm", "budget_usd"}
    assert all(f"- {n}:" in text for n in names)
    assert ANSWERS.drivetrain in text


def test_merge_trusts_the_answer_then_the_bom_then_the_cad_then_the_default():
    found = [
        Found(field="n_drive_motors", value=4, source="cad", evidence="parts"),
        Found(field="n_drive_motors", value=2, source="bom", evidence="row"),
        Found(field="mass_kg", value=7.1, source="cad", evidence="estimate"),
        Found(field="mass_kg", value=20, source="answer", evidence="weighs 20 kg"),
        Found(field="wheel_radius_mm", value=75, source="cad", evidence="parts wheel_left"),
    ]
    rows = {r.field: r for r in merge("wheeled", load_demo_robot(), found).specs}
    assert [r.field for r in rows.values()] == [f.id for f in WHEELED]
    assert (rows["n_drive_motors"].value, rows["n_drive_motors"].source) == (2, "bom")
    assert (rows["mass_kg"].value, rows["mass_kg"].source) == (20, "answer")
    assert (rows["wheel_radius_mm"].value, rows["wheel_radius_mm"].source) == (75, "cad")
    assert (rows["v_max_mps"].value, rows["v_max_mps"].source) == (1.0, "default")
    assert rows["v_max_mps"].evidence is None
    assert rows["wheel_radius_mm"].default == 60 and rows["wheel_radius_mm"].divisor == 1000


def test_default_rows_rebuild_exactly_the_demo_requirements():
    """What the browser does with the rows: value / divisor. It must give back the demo robot's
    numbers bit for bit, or the recorded agent goal no longer matches."""
    demo = load_demo_robot()
    rows = merge("wheeled", demo, []).specs
    rebuilt = RobotRequirements(**{r.robot_field: r.value / r.divisor for r in rows})
    assert rebuilt == demo.requirements


class FakeGemini:
    def __init__(self, reply=None, miss=False):
        self.reply, self.miss, self.prompts = reply, miss, []

    async def extract_json(self, text, schema, temperature=0.0):
        self.prompts.append(text)
        if self.miss:
            raise ReplayMiss("no recording")
        return self.reply


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(settings, "cad_worker_url", "http://cad.invalid")
    with TestClient(app) as c:
        yield c


def use_gemini(client, **by_mode):
    client.app.state.runtime.gemini = lambda mode: by_mode[mode]


def body(answers=None):
    bom = [r.model_dump(mode="json") for r in load_demo_robot().bom]
    return {"bom": bom, "answers": answers.model_dump() if answers else None}


def test_intake_without_answers_runs_only_the_file_rules(client):
    use_gemini(client)  # any Gemini call would raise KeyError
    r = client.post("/api/intake", json=body())
    assert r.status_code == 200
    rows = {row["field"]: row for row in r.json()["specs"]}
    assert rows["n_drive_motors"]["source"] == "bom"
    assert rows["mass_kg"]["source"] == "default" and rows["mass_kg"]["ask"]
    assert r.json()["company"] == []


def test_intake_replays_a_recorded_reading_without_a_token(client, monkeypatch):
    monkeypatch.setattr(settings, "require_live_token", True)
    reply = {"facts": [], "numbers": [number("mass_kg", 44, "lb", "weighs 44 lb")]}
    use_gemini(client, replay=FakeGemini(reply))
    r = client.post("/api/intake", json=body(ANSWERS))
    assert r.status_code == 200
    mass = next(row for row in r.json()["specs"] if row["field"] == "mass_kg")
    assert mass["source"] == "answer" and mass["evidence"] == "weighs 44 lb"
    assert mass["value"] == pytest.approx(19.9581, abs=1e-4)


def test_new_answers_need_the_live_token_on_a_public_deploy(client, monkeypatch):
    monkeypatch.setattr(settings, "require_live_token", True)
    monkeypatch.setattr(settings, "live_jobs_token", "secret")
    monkeypatch.setattr(settings, "gemini_api_key", "g")
    live = FakeGemini(
        {"facts": [fact("company_name", "Acme Robotics", "Acme Robotics")], "numbers": []}
    )
    use_gemini(client, replay=FakeGemini(miss=True), mixed=live)
    assert client.post("/api/intake", json=body(ANSWERS)).status_code == 403
    assert live.prompts == []
    r = client.post("/api/intake", json=body(ANSWERS), headers={"X-Live-Token": "secret"})
    assert r.status_code == 200
    assert r.json()["company"][0]["value"] == "Acme Robotics"


def test_new_answers_without_a_gemini_key_are_a_clear_error(client, monkeypatch):
    monkeypatch.setattr(settings, "require_live_token", False)
    monkeypatch.setattr(settings, "gemini_api_key", "")
    use_gemini(client, replay=FakeGemini(miss=True))
    r = client.post("/api/intake", json=body(ANSWERS))
    assert r.status_code == 503 and "GEMINI_API_KEY" in r.json()["detail"]


def test_cad_upload_passes_the_file_to_the_worker_and_explains_a_bad_one(client):
    def worker(request: httpx.Request) -> httpx.Response:
        if request.content.startswith(b"ISO-10303-21"):
            part = {"name": "wheel_left", "bbox_mm": [120, 25, 120], "volume_mm3": 282743}
            measured = {"parts": [part], "bbox_mm": [120, 25, 120], "volume_mm3": 282743}
            return httpx.Response(200, json=measured)
        return httpx.Response(422, json={"detail": "not a readable STEP file"})

    http = httpx.AsyncClient(transport=httpx.MockTransport(worker))
    client.app.state.runtime.cad = CadClient(http, "http://cad.test")
    ok = client.post("/api/intake/cad", content=b"ISO-10303-21; ...")
    assert ok.status_code == 200 and ok.json()["parts"][0]["name"] == "wheel_left"
    bad = client.post("/api/intake/cad", content=b"junk")
    assert bad.status_code == 422 and bad.json()["detail"] == "not a readable STEP file"


def test_cad_upload_reports_a_worker_that_is_down_and_an_empty_file(client):
    assert client.post("/api/intake/cad", content=b"").status_code == 400
    r = client.post("/api/intake/cad", content=b"ISO-10303-21;")
    assert r.status_code == 502 and "CAD worker" in r.json()["detail"]


@pytest.mark.anyio
async def test_the_example_answers_replay_offline_and_give_the_demo_robot():
    """The demo path: "Use the example" must need no Gemini call and no agent run. That holds
    while the recorded reading matches the current prompt, and its live numbers are the demo's."""
    example = load_example()
    recorder = Recorder(settings.recordings_dir, "replay", replay_speed=0)
    model = Settings.model_fields["gemini_flash_model"].default
    async with httpx.AsyncClient() as http:
        gemini = GeminiClient(recorder, http, "", model)
        raw = await gemini.extract_json(prompt(example, WHEELED), response_schema(WHEELED))
    company, stated, dropped = confirm(raw, example, WHEELED)
    assert dropped == []
    demo = load_demo_robot()
    rows = merge("wheeled", demo, specs_from_bom(demo.bom) + stated, company).specs
    assert {r.field for r in rows if r.source == "answer"} >= {"mass_kg", "v_max_mps"}
    assert all(r.value == r.default for r in rows)
    facts = {c.field: c.value for c in company}
    assert facts["final_assembly_country"] == demo.final_assembly_country
    assert facts["sells_to_us_federal"] == "yes"


def test_example_endpoint_serves_the_shared_file(client):
    assert client.get("/api/intake/example").json() == load_example().model_dump()
