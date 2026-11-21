import asyncio

import pytest

from app.orchestrator.fleet import BudgetExceeded, Fleet, JobBudget

pytestmark = pytest.mark.anyio


async def test_agent_budget_is_enforced():
    fleet, budget = Fleet({"agent": 5}), JobBudget(max_agent_runs=2)
    for _ in range(2):
        async with fleet.slot("agent", budget, "a.com"):
            pass
    with pytest.raises(BudgetExceeded):
        async with fleet.slot("agent", budget, "a.com"):
            pass


async def test_agent_runs_need_a_domain():
    with pytest.raises(ValueError):
        async with Fleet({"agent": 1}).slot("agent", JobBudget()):
            pass


async def test_unconfigured_product_is_an_error():
    with pytest.raises(ValueError):
        async with Fleet({}).slot("fetch", JobBudget()):
            pass


async def peak_concurrency(fleet: Fleet, product, domains) -> int:
    running, peak = 0, 0

    async def one(domain):
        nonlocal running, peak
        async with fleet.slot(product, JobBudget(max_agent_runs=99), domain):
            running += 1
            peak = max(peak, running)
            await asyncio.sleep(0.01)
            running -= 1

    await asyncio.gather(*(one(d) for d in domains))
    return peak


async def test_one_agent_run_per_domain():
    assert await peak_concurrency(Fleet({"agent": 4}), "agent", ["a.com"] * 3) == 1


async def test_slots_cap_concurrency_across_domains():
    domains = ["a.com", "b.com", "c.com", "d.com"]
    assert await peak_concurrency(Fleet({"agent": 2}), "agent", domains) == 2
    assert await peak_concurrency(Fleet({"fetch": 3}), "fetch", [None] * 5) == 3


async def test_queued_domain_does_not_hold_a_slot():
    fleet, order = Fleet({"agent": 1}), []

    async def run(domain, hold):
        async with fleet.slot("agent", JobBudget(), domain):
            order.append(domain)
            await asyncio.sleep(hold)

    await asyncio.gather(run("a.com", 0.03), run("a.com", 0.0), run("b.com", 0.0))
    assert order == ["a.com", "b.com", "a.com"]
