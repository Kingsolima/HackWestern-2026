"""Fleet scheduler (docs/design/04 section 5): account-wide slots per product, at most one agent
run per domain at a time, and per-job budgets enforced in code."""

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator, Mapping
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass

from app.schemas import Product


class BudgetExceeded(RuntimeError):
    pass


@dataclass
class JobBudget:
    max_agent_runs: int = 8
    agent_runs: int = 0

    def charge_agent_run(self) -> None:
        if self.agent_runs >= self.max_agent_runs:
            raise BudgetExceeded(f"agent run budget of {self.max_agent_runs} used up")
        self.agent_runs += 1


class Fleet:
    def __init__(self, slots: Mapping[Product, int]) -> None:
        self._slots = {product: asyncio.Semaphore(n) for product, n in slots.items()}
        self._domain_locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    @asynccontextmanager
    async def slot(
        self, product: Product, budget: JobBudget, domain: str | None = None
    ) -> AsyncIterator[None]:
        """Charges the budget before waiting, so a job cannot queue more runs than it may make.
        Takes the domain lock before the account slot, so a run queued behind its domain does
        not hold a slot idle."""
        semaphore = self._slots.get(product)
        if semaphore is None:
            raise ValueError(f"no slots configured for {product}")
        async with AsyncExitStack() as stack:
            if product == "agent":
                if domain is None:
                    raise ValueError("agent runs need a domain for per-domain politeness")
                budget.charge_agent_run()
                await stack.enter_async_context(self._domain_locks[domain])
            await stack.enter_async_context(semaphore)
            yield
