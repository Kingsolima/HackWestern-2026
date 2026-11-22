import pytest

from app.agents.verifier import canonical_url, lower_tier, origin_class, origin_tier, same_page


@pytest.mark.parametrize(
    ("quote", "expected"),
    [
        (
            "we'll build and ship it to you from our New York manufacturing plant",
            "made_at_named_us_plant",
        ),
        ("produced in our Murphy, NC facility", "made_at_named_us_plant"),
        ("Made in USA", "us_made_site_unstated"),
        ("Proudly made in the U.S.A. since 1987", "us_made_site_unstated"),
        ("Designed and manufactured in the United States", "us_made_site_unstated"),
        ("Teknic designs and builds products in the USA.", "us_made_site_unstated"),
        ("We manufacture every motor in the United States", "us_made_site_unstated"),
        ("Country of Origin USA", "us_made_site_unstated"),
        ("Country of origin: United States", "us_made_site_unstated"),
        ("Assembled in USA", "assembled_in_us"),
        ("Designed in USA", "designed_in_us"),
        ("Engineered in America", "designed_in_us"),
        ("Designed in USA, made in China", "foreign"),
        ("Built at our plant in Taiwan", "foreign"),
        ("Country of origin: China", "foreign"),
        ("Contact us about factory tours", "not_origin"),
        ("Built to order, contact us about our factory", "not_origin"),
        ("Made to order, in our own factory", "not_origin"),
        ("Headquartered in Harleysville, PA", "not_origin"),
    ],
)
def test_origin_class(quote, expected):
    assert origin_class(quote) == expected


@pytest.mark.parametrize("model_specific", [True, False])
def test_designed_in_usa_never_counts_as_us_made(model_specific):
    assert origin_tier(origin_class("Designed in USA"), model_specific) not in ("T1", "T2")


@pytest.mark.parametrize(
    ("cls", "model_specific", "tier"),
    [
        ("made_at_named_us_plant", True, "T1"),
        ("made_at_named_us_plant", False, "T2"),
        ("us_made_site_unstated", True, "T1"),
        ("us_made_site_unstated", False, "T3"),
        ("assembled_in_us", True, "T3"),
        ("us_hq_only", True, "T3"),
        ("designed_in_us", True, "rejected"),
        ("foreign", True, "rejected"),
        ("not_origin", True, "none"),
    ],
)
def test_origin_tier(cls, model_specific, tier):
    assert origin_tier(cls, model_specific) == tier


@pytest.mark.parametrize(
    ("a", "b", "low"),
    [
        ("T1", "T2", "T2"),
        ("T2", "T1", "T2"),
        ("T1", "none", "none"),
        ("T3", "rejected", "rejected"),
    ],
)
def test_model_can_only_lower_the_tier(a, b, low):
    assert lower_tier(a, b) == low


@pytest.mark.parametrize(
    ("a", "b", "same"),
    [
        (
            "https://teknic.com/model-info/X/?model_voltage=75VDC",
            "https://teknic.com/model-info/X",
            True,
        ),
        ("http://www.teknic.com/model-info/X/", "https://teknic.com/model-info/X/#specs", True),
        ("https://teknic.com/model-info/X/", "https://teknic.com/model-info/Y/", False),
        ("https://teknic.com/model-info/X/", "https://other.com/model-info/X/", False),
    ],
)
def test_same_page(a, b, same):
    assert same_page(a, b) is same


def test_canonical_url_in_either_attribute_order():
    assert (
        canonical_url('<link rel="canonical" href="https://a/x?b=1&amp;c=2">')
        == "https://a/x?b=1&c=2"
    )
    assert canonical_url("<link href='https://a/y' rel=canonical>") == "https://a/y"
    assert canonical_url("<link rel='stylesheet' href='https://a/s.css'>") is None


def _candidate(quote, claim_url, product_url, verified=True):
    from datetime import UTC, datetime

    from app.schemas import Candidate, Claim, OriginEvidence, Source

    claim = Claim(
        id="o1",
        candidate_id="m",
        field="country_of_origin",
        raw_value="USA",
        raw_unit=None,
        quote=quote,
        source=Source(url=claim_url, kind="page", fetched_at=datetime.now(UTC), via="tinyfetch"),
        extracted_by="tinyagent",
        verified=verified,
    )
    return Candidate(
        id="m",
        manufacturer="M",
        part_number="P",
        motor_type="servo_integrated",
        nema_frame="23",
        claims=[claim],
        origin=OriginEvidence(country=None, tier="none", claim_id=None),
        status="found",
        product_url=product_url,
    )


def test_origin_row_on_the_models_own_page_is_t1():
    from app.agents.verifier import origin_evidence

    model = "https://teknic.com/model-info/X/"
    got = origin_evidence(_candidate("Country of Origin USA", model + "?v=75", model))
    assert (got.country, got.tier, got.claim_id) == ("US", "T1", "o1")


def test_company_wide_statement_is_t3_and_unverified_is_none():
    from app.agents.verifier import origin_evidence

    about = _candidate(
        "Teknic designs and builds products in the USA.",
        "https://teknic.com/about/",
        "https://teknic.com/model-info/X/",
    )
    assert origin_evidence(about).tier == "T3"
    unverified = _candidate("Country of Origin USA", "https://a/x", "https://a/x", verified=False)
    assert origin_evidence(unverified).tier == "none"


def test_designed_in_usa_is_rejected_even_on_the_model_page():
    from app.agents.verifier import origin_evidence

    got = origin_evidence(_candidate("Designed in USA", "https://a/x", "https://a/x"))
    assert got.tier == "rejected"
