"""Tygo's chunk 3 core: route_page. These fail until it is written.

Spec: docs/design/04 section 3 (TRIAGE), docs/design/07 section 4 (Decision 1, threshold 0.8).
"""

import json
from pathlib import Path

import pytest

from app.agents.triage import CONFIDENCE, TriageInput, route_page

SPECS_MD = "| Cont. (RMS) Torque | 45 oz-in (0.32 N-m) |\n| Peak Torque | 97 oz-in |"


def page(top: str | None = "readable_specs", p: float = 0.95, text: str | None = SPECS_MD, ok=True):
    decision = None
    if top is not None:
        rest = (1 - p) / 3
        labels = ["readable_specs", "needs_interaction", "not_a_product_page", "blocked_or_captcha"]
        decision = {label: (p if label == top else rest) for label in labels}
    return TriageInput(url="https://maker.example/m1", fetch_ok=ok, text=text, decision=decision)


def test_readable_page_with_torque_values_is_readable():
    assert route_page(page()) == "readable"


@pytest.mark.parametrize(
    "text",
    [
        "Rated torque: 0.64 Nm",
        "Continuous torque 1.27 N·m at 3000 rpm",
        "Holding torque 180 mNm",
        "Torque: 26 lb-in",
        "Torque 4.5 kgf-cm",
        "Peak torque 97 OZ-IN",
        "Stall torque 425 oz in",
    ],
)
def test_any_torque_unit_with_a_number_counts(text):
    assert route_page(page(text=text)) == "readable"


@pytest.mark.parametrize(
    "text",
    [
        "Peak Torque | | Cont. (RMS) Torque | |",
        "Torque curves for every model are shown below.",
        "Torque (oz-in)",
        "Rotor inertia 0.4 oz-in² is low",
    ],
)
def test_readable_label_without_torque_values_needs_the_agent(text):
    assert route_page(page(text=text)) == "needs_interaction"


def test_low_confidence_needs_the_agent():
    assert route_page(page(p=CONFIDENCE - 0.05)) == "needs_interaction"


def test_threshold_is_inclusive():
    assert route_page(page(p=CONFIDENCE)) == "readable"


def test_confident_non_product_page_is_dead():
    assert route_page(page(top="not_a_product_page")) == "dead"


def test_unsure_non_product_page_is_not_dead():
    assert route_page(page(top="not_a_product_page", p=0.6)) == "needs_interaction"


@pytest.mark.parametrize("top", ["blocked_or_captcha", "needs_interaction"])
def test_blocked_and_interactive_pages_go_to_the_agent(top):
    assert route_page(page(top=top)) == "needs_interaction"


@pytest.mark.parametrize(
    "kw",
    [{"ok": False, "text": None}, {"text": None}, {"text": ""}, {"top": None}],
)
def test_missing_inputs_fall_back_to_the_agent(kw):
    assert route_page(page(**kw)) == "needs_interaction"


def test_real_teknic_fetch_is_not_readable_even_if_the_model_says_so():
    # Fresh Fetch html of a Teknic model page: the torque cells are filled by JavaScript.
    fixture = Path(__file__).parent / "fixtures" / "teknic" / "fetch_tables.json"
    text = json.loads(fixture.read_text())["response"]["results"][0]["text"]
    assert route_page(page(text=text)) == "needs_interaction"
