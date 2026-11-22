from app.engineering.ranking import RankInput, rank
from app.engineering.spec_checks import SpecCheck


def design(cid, verdict="pass", price=100.0, tier="none", margin=1.5):
    check = SpecCheck(
        candidate_id=cid,
        check="torque_cont",
        verdict="pass",
        value=1,
        threshold=1,
        unit="N·m",
        margin=margin,
        claim_ids=[],
        note="",
    )
    return RankInput(
        candidate_id=cid, verdict=verdict, price_usd=price, origin_tier=tier, checks=[check]
    )


def test_each_objective_picks_its_best():
    wins = rank(
        [
            design("cheap", price=100, tier="T3", margin=1.1),
            design("strong", price=400, tier="T2", margin=3.0),
            design("us", price=300, tier="T1", margin=1.2),
        ]
    )
    assert wins == {"cheap": ["cost"], "strong": ["performance"], "us": ["us_first"]}


def test_rejected_never_ranks_and_review_only_when_nothing_passes():
    wins = rank(
        [design("bad", verdict="rejected", price=1), design("rev", verdict="review", price=50)]
    )
    assert wins["bad"] == [] and "cost" in wins["rev"]
    wins = rank([design("ok", price=500), design("rev", verdict="review", price=50)])
    assert wins["rev"] == [] and wins["ok"] == ["cost", "performance"]


def test_us_first_needs_t1_or_t2():
    wins = rank([design("hq", tier="T3"), design("none")])
    assert all("us_first" not in w for w in wins.values())


def test_missing_price_cannot_win_cost():
    wins = rank([design("noprice", price=None), design("priced", price=999)])
    assert "cost" in wins["priced"]
