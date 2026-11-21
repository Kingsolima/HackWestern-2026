# 06 Reading list: orchestration, agent architecture, TinyFish (Tygo)

Ordered by what you need first. Times are rough.

## Hour 1: TinyFish, the parts you will call (~60 min)

1. For Coding Agents (single page: SDKs, endpoints, latencies, gotchas) - 10 min
   https://docs.tinyfish.ai/for-coding-agents.md
2. TinyAgent endpoints: run vs run-async vs run-batch vs run-sse; common request options
   (`agent_config.max_duration_seconds`, `capture_config.html`, `webhook_url`) - 10 min
   https://docs.tinyfish.ai/tinyagent/api/agent/endpoints.md
3. Runs: lifecycle, statuses, how a run ends (why COMPLETED != success) - 5 min
   https://docs.tinyfish.ai/tinyagent/explanation/runs.md
4. Structured-output schema rules (nullable, no type arrays, keyword allowlist) - 5 min
   https://docs.tinyfish.ai/tinyagent/api/agent/structured-output.md
5. Goal prompting guide (goal quality drives success rate) - 10 min
   https://docs.tinyfish.ai/prompting-guide.md
6. Live browser preview (STREAMING_URL event -> iframe) - 3 min
   https://docs.tinyfish.ai/live-preview.md
7. Anti-bot guide (diagnose block vs bad goal; stealth + proxy) - 7 min
   https://docs.tinyfish.ai/anti-bot-guide.md
8. Fetch and Search references (10 URLs per Fetch call, formats, `ttl=0`, rate limits) - 10 min
   https://docs.tinyfish.ai/tinyfetch/reference.md
   https://docs.tinyfish.ai/tinysearch/reference.md

Skim later: Error codes https://docs.tinyfish.ai/error-codes.md, Webhooks
https://docs.tinyfish.ai/webhooks.md, TinyMonitor https://docs.tinyfish.ai/tinymonitor/index.md,
TinyBrowser https://docs.tinyfish.ai/tinybrowser/index.md, TinySet https://docs.tinyfish.ai/tinyset/index.md,
cookbook https://github.com/tinyfish-io/tinyfish-cookbook.
Whole docs in one file (grep it, don't read it): https://docs.tinyfish.ai/llms-full.txt

Facts worth memorizing (from llms-full.txt, Nov 21):
- Free daily allowance: 12,000 Search requests, 1,000 Fetch URLs (reset 00:00 UTC); per-minute
  limits exist (example error shows 30 Search requests/min).
- Agent concurrency is per account; extra runs queue, a pending-run cap returns 429 without
  Retry-After. TinyFish does not throttle per domain: we must.
- `capture_config.html` is open to everyone; screenshots/snapshots "haven't shipped";
  recording is enterprise-only. `max_steps` and `strict` mode are beta.
- Statuses: PENDING, RUNNING, COMPLETED, FAILED, CANCELLED. Sync `/run` runs cannot be cancelled.
- A timed-out call may still be running: look it up before re-running.

## Hour 2: agent architecture (~50 min)

1. Anthropic, "Building effective agents" - workflows vs agents, orchestrator-workers,
   evaluator-optimizer. Our design is an orchestrator-workers workflow. 15 min
   https://www.anthropic.com/engineering/building-effective-agents
2. 12-factor agents, especially factors 4 (tools are structured outputs), 8 (own your control
   flow), 10 (small focused agents). 15 min
   https://github.com/humanlayer/12-factor-agents
3. Anthropic, "How we built our multi-agent research system" - parallel workers, effort
   budgets, how the lead agent fails. 15 min
   https://www.anthropic.com/engineering/built-multi-agent-research-system
4. Cemri et al., "Why Do Multi-Agent LLM Systems Fail?" (MAST) - read the taxonomy figure and
   the verification section; it justifies the verifier and code-owned control flow. 10 min
   https://arxiv.org/abs/2503.13657

Added for the v3 architecture (07): read the abstracts and key figures, ~30 min total.
5. Kim et al., "Towards a Science of Scaling Agent Systems" - when multi-agent helps (decomposable)
   vs hurts (sequential, tool-heavy), error amplification by topology. https://arxiv.org/abs/2512.08296
6. Salemi et al., blackboard multi-agent system - the shared-memory pattern we borrow.
   https://arxiv.org/abs/2510.01285
7. Zhang et al., "Stop overvaluing multi-agent debate" - why synthesis is bounded.
   https://arxiv.org/abs/2502.08788
8. Gemini Decisions API (question types, confidence, "atomic checks composed in code").
   https://ai.google.dev/gemini-api/docs/decisions-api
9. TimescaleDB real-time aggregates (off by default since 2.13).
   https://docs.timescale.com/use-timescale/latest/continuous-aggregates/real-time-aggregates

## Hour 3: the other pieces you touch (~30 min)

- Gemini document understanding (PDFs up to 1000 pages, tables, charts)
  https://ai.google.dev/gemini-api/docs/document-processing
- Gemini structured output https://ai.google.dev/gemini-api/docs/structured-output
- Tiger Data continuous aggregates (for `site_success_hourly`)
  https://docs.tigerdata.com/use-timescale/latest/continuous-aggregates/create-a-continuous-aggregate
- FastAPI SSE via sse-starlette https://github.com/sysid/sse-starlette

## Supply-chain factors (you own the math)

- `02-sourcing-factors.md` in this folder: tariff stack, FCC test, rare earths, UFLPA, dates.
- 48 CFR 25.003 definitions (cost of components, unknown origin = foreign)
  https://www.ecfr.gov/current/title-48/chapter-1/subchapter-D/part-25/subpart-25.0/section-25.003
- Sentinel Automata worked example of the 65% test
  https://automata.llc/blog/fcc-covered-list-robots-65-percent-test/
- HTSBase, Section 301 layers in 2026 https://htsbase.com/blog/section-301-china-tariffs-2026
- USITC HTS search (hand-verify the 2-3 HTS codes in `tariffs.yaml`) https://hts.usitc.gov/
