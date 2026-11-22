"""INTAKE and CRITERIA stages (docs/BUILD-PLAN-v4.md section 3). Both are no-ops on v3 jobs
that have no project."""

import time
from collections.abc import Sequence

import httpx

from app.agents.intake import INTAKE_PROMPT, INTAKE_SCHEMA, merge_facts, page_facts
from app.engineering.criteria import derive_criteria
from app.orchestrator.context import JobContext
from app.orchestrator.discovery import TRIAGE_CHARS
from app.orchestrator.events import (
    ClaimRejected,
    ClaimVerified,
    ProjectPayload,
    ProjectView,
    RunFinished,
    RunProgress,
    RunStarted,
)
from app.tfclient.recorder import ReplayMiss


async def intake(ctx: JobContext, workers: Sequence[object]) -> None:
    """Read the company's own pages (one TinyFetch call), let Flash propose facts with quotes,
    keep those whose quote verifies on the same page."""
    project = ctx.project
    if project is None or not project.intake_sources:
        return
    urls = [s.url for s in project.intake_sources]
    run_id = f"{ctx.job_id}:intake"
    start = time.monotonic()
    async with ctx.fleet.slot("fetch", ctx.budget):
        fetched = await ctx.tf.fetch(urls)
    await ctx.log.emit(
        RunStarted(
            run_id=run_id,
            worker="intake",
            product="fetch",
            site="fetch.tinyfish.ai",
            url=None,
            goal=f"Read {len(urls)} {project.name} pages for facts about {project.robot}",
            live=fetched.live,
        )
    )
    texts = {r.url: r.text for r in fetched.results if isinstance(r.text, str)}
    read = 0
    for n, url in enumerate(urls):
        text = texts.get(url)
        if not text:
            await ctx.log.emit(RunProgress(run_id=run_id, purpose=f"not read: {url}"))
            continue
        prompt = INTAKE_PROMPT.format(
            company=project.name, robot=project.robot, url=url, text=text[:TRIAGE_CHARS]
        )
        try:
            async with ctx.fleet.slot("gemini", ctx.budget):
                raw = await ctx.gemini.extract_json(prompt, INTAKE_SCHEMA)
        except (httpx.HTTPError, ReplayMiss, ValueError, KeyError) as exc:
            await ctx.log.emit(RunProgress(run_id=run_id, purpose=f"facts not read: {exc}"))
            continue
        read += 1
        facts, claims = page_facts(raw, project.id, url, text[:TRIAGE_CHARS], f"{run_id}:{n}")
        for claim in claims:
            if claim.verified:
                await ctx.log.emit(ClaimVerified(claim=claim))
            else:
                await ctx.log.emit(ClaimRejected(claim=claim, reason="quote not on the page"))
        ctx.verified_facts.extend(facts)
    await ctx.log.emit(
        RunFinished(
            run_id=run_id,
            outcome="success" if read == len(urls) else "incomplete",
            reason=f"{read} of {len(urls)} pages read, {len(ctx.verified_facts)} facts verified",
            duration_s=round(time.monotonic() - start, 3),
            live=fetched.live,
        )
    )


async def criteria(ctx: JobContext, workers: Sequence[object]) -> None:
    project = ctx.project
    if project is None:
        return
    facts, used = merge_facts(project.stated, ctx.verified_facts)
    ctx.criteria = derive_criteria(facts)
    await ctx.log.emit(
        ProjectPayload(
            project=ProjectView(
                id=project.id,
                kind=project.kind,
                name=project.name,
                robot=project.robot,
                use_case=project.use_case,
                robot_kind=project.robot_kind,
                robot_params=(project.arm or project.wheeled).model_dump()
                if (project.arm or project.wheeled)
                else {},
                deep_line=project.deep_line,
                bom=project.bom,
                facts=facts,
                fact_basis=used,
            ),
            criteria=ctx.criteria,
        )
    )
