import json
import typing

import pytest
from pydantic import ValidationError

from app.config import REPO_ROOT
from app.schemas import AgentMotorCandidate, BoardEntry, Spec

TF_SCHEMA = json.loads(
    (REPO_ROOT / "docs/design/schemas/motor_candidate.tinyfish.json").read_text()
)


def literal_values(model, field: str) -> set[str]:
    annotation = model.model_fields[field].annotation
    if typing.get_origin(annotation) is not typing.Literal and typing.get_args(annotation):
        annotation = next(a for a in typing.get_args(annotation) if a is not type(None))
    if typing.get_origin(annotation) is typing.Literal:
        return set(typing.get_args(annotation))
    return {member.value for member in annotation}


def test_agent_candidate_fields_mirror_tinyfish_schema():
    assert set(AgentMotorCandidate.model_fields) == set(TF_SCHEMA["properties"])
    spec_props = TF_SCHEMA["properties"]["specs"]["items"]["properties"]
    assert set(Spec.model_fields) == set(spec_props)


@pytest.mark.parametrize(
    ("model", "field", "schema_enum"),
    [
        (AgentMotorCandidate, "status", TF_SCHEMA["properties"]["status"]["enum"]),
        (AgentMotorCandidate, "motor_type", TF_SCHEMA["properties"]["motor_type"]["enum"]),
        (AgentMotorCandidate, "nema_frame", TF_SCHEMA["properties"]["nema_frame"]["enum"]),
        (Spec, "name", TF_SCHEMA["properties"]["specs"]["items"]["properties"]["name"]["enum"]),
    ],
)
def test_enums_mirror_tinyfish_schema(model, field, schema_enum):
    assert literal_values(model, field) == set(schema_enum)


def test_agent_candidate_accepts_all_null_output():
    nulls = {k: None for k in TF_SCHEMA["required"]} | {
        "status": "not_found",
        "reason": "no such page",
        "specs": [],
    }
    assert AgentMotorCandidate.model_validate(nulls).manufacturer is None


def entry(**kw) -> BoardEntry:
    base = dict(job_id="j", author="verifier", kind="fact", subject="m", payload={}, verified=True)
    return BoardEntry(**(base | kw))


def test_only_verifier_writes_verified_facts():
    assert entry().kind == "fact"
    with pytest.raises(ValidationError):
        entry(author="swap:drive_motor")
    with pytest.raises(ValidationError):
        entry(verified=False)


def test_workers_may_post_hints():
    assert entry(author="swap:drive_motor", kind="hint", verified=False).kind == "hint"
