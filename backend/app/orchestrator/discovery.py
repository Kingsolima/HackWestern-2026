"""PLAN, DISCOVER and TRIAGE for the swap line (docs/design/04 section 3).

Free TinySearch and TinyFetch cast the wide net; Gemini Decision 1 plus code rules route each
page; only pages that need clicking go to paid TinyAgent runs. Queries are built by code from
the requirement, so they are reproducible and replayable.
"""

import time
from urllib.parse import urlparse

import httpx

from app.agents.triage import Lead, TriageInput, TriageLabel, route_page
from app.orchestrator.context import JobContext
from app.orchestrator.events import RunFinished, RunProgress, RunStarted
from app.schemas import Project
from app.tfclient.recorder import ReplayMiss

EXCLUDED_DOMAINS = (
    "amazon.",
    "ebay.",
    "alibaba.",
    "aliexpress.",
    "made-in-china.",
    "walmart.",
    "youtube.",
    "reddit.",
    "wikipedia.",
    "facebook.",
    "linkedin.",
    "pinterest.",
    "instagram.",
    "x.com",
    "twitter.",
)
PER_DOMAIN = 2
MAX_LEADS = 8
FETCH_BATCH = 10
TRIAGE_CHARS = 30_000

TRIAGE_QUESTION = (
    "This is the text of a web page found while searching for a NEMA 23 servo or brushless "
    "motor to buy. Can the motor's specifications be read directly from this text?"
)
TRIAGE_OPTIONS: dict[TriageLabel, str] = {
    "readable_specs": "A page for one specific motor model whose text shows its specifications "
    "(torque, speed, voltage) as numbers.",
    "needs_interaction": "A product or product-family page where the specifications need "
    "clicking: model selectors, tabs, configurators, or a model list leading to spec pages.",
    "not_a_product_page": "Not a motor product page: news, forum, blog, marketplace, "
    "directory, or a different kind of product.",
    "blocked_or_captcha": "A bot check, CAPTCHA, access-denied or error page instead of content.",
}


def plan_queries(project: Project | None = None) -> list[str]:
    """v3 jobs look for US-made motors; project jobs look for any maker of the deep line's frame,
    since origin is one risk factor among several (BUILD-PLAN-v4 section 1)."""
    if project is None:
        return [
            "NEMA 23 servo motor made in USA",
            "NEMA 23 integrated servo motor manufactured in the United States",
            "US made NEMA 23 brushless DC motor 24V",
        ]
    f = project.deep_frame
    return [
        f"NEMA {f} servo motor manufacturer datasheet",
        f"NEMA {f} closed loop stepper motor manufacturer",
        f"NEMA {f} integrated servo motor price",
    ]


def domain_of(url: str) -> str:
    return (urlparse(url).hostname or "").removeprefix("www.")


def keep_leads(urls: list[tuple[str, str | None]]) -> list[Lead]:
    """Drop marketplaces and social sites, at most PER_DOMAIN pages per site, MAX_LEADS total,
    in search-rank order."""
    leads: list[Lead] = []
    seen: set[str] = set()
    per_domain: dict[str, int] = {}
    for url, title in urls:
        domain = domain_of(url)
        if not domain or url in seen or any(x in domain for x in EXCLUDED_DOMAINS):
            continue
        if per_domain.get(domain, 0) >= PER_DOMAIN:
            continue
        seen.add(url)
        per_domain[domain] = per_domain.get(domain, 0) + 1
        leads.append(Lead(url=url, domain=domain, title=title))
        if len(leads) == MAX_LEADS:
            break
    return leads


async def discover(ctx: JobContext, queries: list[str]) -> list[Lead]:
    found: list[tuple[str, str | None]] = []
    for i, query in enumerate(queries):
        run_id = f"{ctx.job_id}:search:{i}"
        start = time.monotonic()
        async with ctx.fleet.slot("search", ctx.budget):
            result = await ctx.tf.search(query, location="US")
        await ctx.log.emit(
            RunStarted(
                run_id=run_id,
                worker="discover",
                product="search",
                site="search.tinyfish.ai",
                url=None,
                goal=query,
                live=result.live,
            )
        )
        found.extend((r.url, r.title) for r in result.results)
        await ctx.log.emit(
            RunFinished(
                run_id=run_id,
                outcome="success" if result.results else "not_found",
                reason=f"{len(result.results)} results",
                duration_s=round(time.monotonic() - start, 3),
                live=result.live,
            )
        )
    return keep_leads(found)


async def classify(ctx: JobContext, run_id: str, text: str) -> dict[TriageLabel, float] | None:
    """Decision 1 probabilities, or None when the call fails (no key live, or not recorded in
    replay): route_page then sends the page to the agent, the safe default either way."""
    try:
        async with ctx.fleet.slot("gemini", ctx.budget):
            answer = await ctx.gemini.choose(
                text[:TRIAGE_CHARS], TRIAGE_QUESTION, dict(TRIAGE_OPTIONS)
            )
    except (httpx.HTTPError, ReplayMiss) as exc:
        await ctx.log.emit(RunProgress(run_id=run_id, purpose=f"Decision 1 unavailable: {exc}"))
        return None
    return {label: answer.probabilities.get(label, 0.0) for label in TRIAGE_OPTIONS}


async def triage(ctx: JobContext, leads: list[Lead]) -> list[Lead]:
    """Fetch every lead as markdown (free, 10 URLs per call), ask Decision 1 what kind of page
    it is, and let route_page decide."""
    routed: list[Lead] = []
    for b in range(0, len(leads), FETCH_BATCH):
        batch = leads[b : b + FETCH_BATCH]
        run_id = f"{ctx.job_id}:fetch:{b // FETCH_BATCH}"
        start = time.monotonic()
        async with ctx.fleet.slot("fetch", ctx.budget):
            fetched = await ctx.tf.fetch([lead.url for lead in batch])
        await ctx.log.emit(
            RunStarted(
                run_id=run_id,
                worker="triage",
                product="fetch",
                site="fetch.tinyfish.ai",
                url=None,
                goal=f"Read {len(batch)} pages",
                live=fetched.live,
            )
        )
        texts = {r.url: r.text for r in fetched.results if isinstance(r.text, str)}
        for lead in batch:
            text = texts.get(lead.url)
            decision = await classify(ctx, run_id, text) if text else None
            route = route_page(
                TriageInput(url=lead.url, fetch_ok=text is not None, text=text, decision=decision)
            )
            routed.append(lead.model_copy(update={"route": route, "text": text}))
            await ctx.log.emit(RunProgress(run_id=run_id, purpose=f"{route}: {lead.url}"))
        await ctx.log.emit(
            RunFinished(
                run_id=run_id,
                outcome="success",
                reason=f"{len(texts)} of {len(batch)} pages read",
                duration_s=round(time.monotonic() - start, 3),
                live=fetched.live,
            )
        )
    return routed
