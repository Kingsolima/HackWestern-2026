# 07 Agent architecture v3: coordinator, blackboard, synthesis

Status: APPROVED Sat Nov 21 ~5pm EST; v3.1 site status ~5:30pm; v3.2 advocates restored with a tight contract ~6pm. Final for build. Extends 04 (pipeline, data shapes, fleet
scheduler stay as written). Diagram: `architecture.html` (open in a browser).

## 1. Which coordinator-subagent pattern, and why

| Pattern | Evidence | Fit for us | Verdict |
|---|---|---|---|
| Orchestrator-workers (lead + parallel subagents) | Anthropic research system; Kim et al. 2025: +80.8% vs single agent on decomposable tasks, central verification limits error spread to 4.4x vs 17.2x for independent agents | BOM lines and candidate pages are independent lookups | Core pattern |
| Blackboard (shared memory, agents post and volunteer) | Salemi et al. 2025: 13-57% end-to-end gain over master-slave when the controller cannot know every subagent's knowledge | Workers learn things others need (blocked sites, supplier origin, datasheet URLs) | Adopt the shared memory; volunteering only for gap tasks |
| Multi-agent debate | Du et al. 2023 shows gains; Zhang et al. 2025 and Smit et al. 2023: MAD does not reliably beat single-agent CoT/self-consistency at higher cost | Our "right answer" is computed by code; debate cannot improve a torque check | Reject debate; synthesis is one writer + critic + gap loop |
| Evaluator-optimizer | Anthropic "Building effective agents" | Report quality and evidence gaps | Critic loop, 1 round |
| Decentralized / peer-to-peer | Kim et al.: worse error propagation without a central check; tool-heavy tasks pay coordination overhead | Many tool calls per worker | Reject |

Caveat from Kim et al. that applies to us: tool-heavy tasks lose from multi-agent overhead.
We avoid most of it because workers are code loops, not LLM agents messaging each other;
coordination goes through structured rows, not chat.

## 2. Roles

- Orchestrator (code): plans with Gemini, posts tasks, owns budgets and stop rules, runs the
  synthesis loop, decides when to stop.
- Part workers (code loops, one per BOM line): swap worker for the drive motor; origin workers
  for 2-3 other high-cost lines (battery, compute, lidar) whose job is to prove current origin
  (unknown = foreign, so proving US origin raises the score at $0). Each worker dispatches
  TinyFish runs, reads the board between runs, posts hints, sends raw claims to the Verifier.
- Verifier (code gate): the only writer of `kind='fact'` rows.
- Case builder (code): per ranked design, strengths vs the other designs and weaknesses (Review
  checks, thinnest margins, weakest origin tier, missing fields), each tied to claim ids.
- Advocates (Gemini Flash, 3, one per objective): choose and phrase items from their own design's
  case lists; contract in section 5. No tools, no numbers, no verdicts.
- Synthesizer (Gemini Flash, one call): writes the comparison, report and RFQ draft from the case
  builder output and the validated advocate outputs; numbers rendered by code.
- Critic (Gemini Decision 1): rubric on the draft and gap finder; answers are composed in code.

## 3. Blackboard on Tiger Data

Answer to "can a continuous aggregate be the shared sketchpad": partly. Continuous aggregates
are read-only materialized views over a hypertable. The writable sketchpad is the `board`
hypertable; the continuous aggregates are shared summaries every worker and job reads. Since
TimescaleDB 2.13 real-time aggregation is off by default; we turn it on
(`materialized_only = false`) so reads include rows newer than the last refresh.

What workers share (concrete):
- supplier facts: "Teknic: T2 origin, NY plant" -> any other Teknic line reuses it.
- datasheet URLs and fetched-object keys -> no duplicate fetches.
- FX rate, tariff lookups -> written once.
- gap requests from the critic -> leased by an idle worker.

Site status has one source of truth: `agent_runs`, which every TinyFish call already writes.
It is not a board kind. In-job decisions do not need the database at all: the orchestrator
dispatches every run and receives every outcome, so it keeps a per-domain circuit breaker in
memory. Rule: two `blocked` outcomes on a domain within 10 minutes, the second after the stealth
+ US proxy retry, opens the breaker: queued tasks for that domain are held, in-flight runs on it
are cancelled (`/run-sse` and `/run-async` runs are cancellable), and the worker is told to use
an alternate source (manufacturer site instead of the distributor). After 10 minutes one probe
run may close it. Every transition is logged to `agent_runs`, so the UI and later jobs see it.

Limits to state honestly:
- A TinyFish run cannot read the board mid-run. Workers read it between dispatches and fold it
  into the next goal ("skip pages already checked: ...", "origin for Teknic already known").
- Facts on the board are as good as the Verifier; hints are labelled unverified.

```sql
-- writable sketchpad
CREATE TABLE board (
  time      timestamptz NOT NULL DEFAULT now(),
  job_id    text NOT NULL,
  author    text NOT NULL,            -- 'swap:drive_motor', 'origin:battery', 'verifier', 'critic', 'monitor'
  bom_line  text,                     -- NULL = relevant to every line
  kind      text NOT NULL CHECK (kind IN ('fact','hint','supplier','gap_request')),
  subject   text NOT NULL,            -- domain, manufacturer or candidate id
  payload   jsonb NOT NULL,
  claim_id  text,
  verified  boolean NOT NULL DEFAULT false,
  CHECK (kind <> 'fact' OR (verified AND author = 'verifier'))
);
SELECT create_hypertable('board', by_range('time'));
CREATE INDEX ON board (job_id, kind, subject, time DESC);

-- work queue (plain table; leases)
CREATE TABLE tasks (
  id bigserial PRIMARY KEY, job_id text NOT NULL, kind text NOT NULL, bom_line text,
  payload jsonb NOT NULL, status text NOT NULL DEFAULT 'open',
  leased_by text, leased_at timestamptz, created_at timestamptz NOT NULL DEFAULT now()
);
-- lease one task:
-- UPDATE tasks SET status='leased', leased_by=$1, leased_at=now()
-- WHERE id = (SELECT id FROM tasks WHERE job_id=$2 AND status='open'
--             ORDER BY id FOR UPDATE SKIP LOCKED LIMIT 1) RETURNING *;

-- typed time series
CREATE TABLE agent_runs (time timestamptz NOT NULL, run_id text, job_id text, product text,
  site text, outcome text, duration_s double precision, steps int, live boolean);
SELECT create_hypertable('agent_runs', by_range('time'));
CREATE TABLE supplier_obs (time timestamptz NOT NULL, manufacturer text, part_number text,
  origin_tier smallint, price_usd double precision, lead_time_days double precision, claim_id text);
SELECT create_hypertable('supplier_obs', by_range('time'));

-- summaries (CASE instead of FILTER, which older caggs rejected)
-- site_success_1h: UI "success rate by site" panel only (TinyFish evidence); agents never read it
CREATE MATERIALIZED VIEW site_success_1h
WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
SELECT time_bucket('1 hour', time) AS bucket, site,
       count(*) AS runs,
       sum(CASE WHEN outcome = 'success' THEN 1 ELSE 0 END) AS ok,
       sum(CASE WHEN outcome = 'blocked' THEN 1 ELSE 0 END) AS blocked,
       avg(duration_s) AS avg_s
FROM agent_runs GROUP BY bucket, site;

CREATE MATERIALIZED VIEW supplier_1h
WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
SELECT time_bucket('1 hour', time) AS bucket, manufacturer,
       last(origin_tier, time) AS origin_tier,
       min(price_usd) AS min_price_usd,
       last(lead_time_days, time) AS lead_time_days
FROM supplier_obs GROUP BY bucket, manufacturer;

SELECT add_continuous_aggregate_policy('site_success_1h', start_offset => INTERVAL '7 days',
  end_offset => INTERVAL '1 hour', schedule_interval => INTERVAL '5 minutes');
SELECT add_continuous_aggregate_policy('supplier_1h', start_offset => INTERVAL '7 days',
  end_offset => INTERVAL '1 hour', schedule_interval => INTERVAL '5 minutes');
```
Untested: run this on Tiger Cloud in hour one (syntax `by_range` needs TimescaleDB 2.13+).

## 4. Gemini Decision 1 (released Nov 11, 2026)

What it is: `gemini-decision-1` via `POST /v1beta/decisions`. Up to 1,000 typed questions over one
shared input (text, PDF, images; 262,144 tokens): yes/no, choice (2-255 options) or score
(ordered rubric). Returns calibrated probabilities plus confidence and zero output tokens.
$0.10 per 1M input tokens; free tier 10,000 requests/day. No text generation and no structured
output, so it cannot replace Flash for extraction or writing. Google's own guidance: "atomic
checks, composed in code", which matches our rule. Vendor claims (150-250 ms, best calibration)
are unverified; Artificial Analysis ranked it 10th of 19 on its Decision Index on launch day.
So we use it only where a wrong answer is cheap and code has the last word.

| Use | Question type | Code composes it how |
|---|---|---|
| Triage router over fetched markdown | choice: readable_specs / needs_interaction / not_a_product_page / blocked_or_captcha | confidence < 0.8 -> send to TinyAgent (safe default) |
| Run outcome check | yes/no: "Does this page show a bot challenge, CAPTCHA or access denied?" | sets `blocked` vs `not_found` for retry policy |
| Origin statement class | choice: made_at_named_us_plant / us_made_site_unstated / assembled_in_us / designed_in_us / us_hq_only / foreign / not_origin | tier = min(code-rule tier, model tier); quote must still match the page verbatim |
| Report rubric (critic) | score 0-3 per draft: evidence cited, trade-offs stated, caveats present, consistent with check table | any score < 2 -> one revision |
| Gap finder | choice over the missing-field list code builds for each design | top choice becomes a `gap_request` task with a concrete field |

Never used for: pass/fail, origin tier above what code allows, any number.

## 5. Synthesis loop (v3.2)

```
facts + checks + compliance + ranked designs
  -> case builder (code): per design, strengths[] and weaknesses[] items, each
     {item_id, kind, claim_ids, detail}; also missing_fields[]
  -> round 1: 3 advocates in parallel (Flash, strict JSON, schemas/advocate_output.schema.json)
  -> round 2 (cross-exam): each advocate sees the other two round-1 outputs + their weakness
     lists, may add <= 2 rebuttals
  -> code validates every advocate item (rules below), drops invalid ones
  -> synthesizer (Flash, one call): comparison + report + RFQ draft
  -> critic (Decision 1): rubric on advocates + synthesizer, gap finder over missing_fields
       rubric score < 2 -> one revision of that output
       gaps and budget left -> orchestrator posts <= 3 gap tasks -> workers -> Verifier ->
       checks + case builder re-run -> advocates and synthesizer re-run once
  -> final report; numbers rendered by code
```

Advocate contract (validated in code; an item that breaks a rule is dropped, an output with no
valid strength falls back to a code template):
1. Input: its own design's case lists, the shared fact table (claim id, field, rendered value),
   and in round 2 the other two round-1 outputs. No raw web text, no tools.
2. May only reference `item_id`s: strengths and concessions from its own design's lists,
   rebuttals from a target design's weakness list.
3. 1-3 strengths, 1-2 concessions (must concede at least one weakness), 0 rebuttals in round 1,
   at most 2 in round 2.
4. No digits in any text field except inside slots `{{claim:ID}}` or `{{part:CANDIDATE_ID}}`,
   which code renders from verified values. Regex check after removing slots: no `[0-9]`.
5. Every slot id must exist and belong to a cited item. Length caps: headline 15 words,
   phrasing 25 words, best_for 25 words.
6. Cannot change ranking, verdicts, fit badges or compliance; the UI shows those from code next
   to the advocate text.
7. Budget: 6 Flash calls total (3 per round), temperature <= 0.3, one revision max via critic.

What the advocates add over a single writer: each design gets a pitch written from its own
objective (what a cost-focused vs a US-first buyer cares about), concessions are forced into the
open per design, and the cross-exam pairs every pitch with the strongest code-listed objection
from a rival. All content is still selected from code-built lists.

## 6. Decisions (recommendation first)

1. Centralized orchestrator-workers with workers as code loops. Alt: LLM subagents that plan
   their own tool calls. Rejected: coordination overhead on tool-heavy work, cost, nondeterminism.
2. Blackboard = `board` hypertable + `tasks` table + 2 real-time continuous aggregates. Alt: the
   continuous aggregate itself as the sketchpad. Rejected: aggregates are read-only views.
3. Only the Verifier writes facts (DB check constraint). Alt: workers write facts directly.
   Rejected: that is the unchecked propagation path measured at 17.2x.
4. Synthesis = code case builder + 3 scoped advocates (2 rounds) + one Flash writer + Decision 1
   critic + one gap round. Advocates kept by Tygo's call (v3.2) with the contract in section 5.
   Alt: free debate (rejected: no reliable gain over single-agent baselines, unbounded cost).
   Alt: no advocates (considered in v3.1; their selection work is code-built either way).
7. Site status only in `agent_runs`; orchestrator circuit breaker in memory; `site_success_1h`
   is a UI panel. Alt: `site_status` board rows + a cagg read by the scheduler. Rejected: two
   sources of truth for one fact, and the orchestrator already sees every outcome first-hand.
5. Decision 1 for routing, origin wording, rubric, gap choice; Flash for extraction and prose.
   Alt: Flash for everything. Rejected: Decision 1 gives calibrated confidence for thresholds and
   costs less; also a fresh-model story for the Gemini prize.
6. Origin workers for 2-3 lines in addition to the motor swap. Alt: motor only. Rejected: the
   parallel fan-out and the shared board only show value with more than one worker. Cut first if
   behind.

## 7. Scope tiers (unchanged freeze at 4am)

- Must: orchestrator, swap worker, verifier, board table, checks, CAD.
- Should: 2 origin workers, circuit breaker, case builder + advocates round 1 + synthesizer,
  site_success_1h panel.
- Could: advocates round 2 (cross-exam), Decision 1 critic and gap round, supplier_1h.

## Sources

- Anthropic, Building effective agents: https://www.anthropic.com/engineering/building-effective-agents
- Anthropic, multi-agent research system: https://www.anthropic.com/engineering/built-multi-agent-research-system
- Kim et al., Towards a Science of Scaling Agent Systems: https://arxiv.org/abs/2512.08296
- Salemi et al., LLM-based multi-agent blackboard system: https://arxiv.org/abs/2510.01285
- Du et al., multi-agent debate: https://arxiv.org/abs/2305.14325
- Zhang et al., Stop overvaluing multi-agent debate: https://arxiv.org/abs/2502.08788
- Smit et al., Should we be going MAD?: https://arxiv.org/abs/2311.17371
- Cemri et al., MAST: https://arxiv.org/abs/2503.13657
- Cognition, Don't build multi-agents: https://cognition.ai/blog/dont-build-multi-agents
- Gemini Decisions API docs: https://ai.google.dev/gemini-api/docs/decisions-api
- Gemini Decision 1 model page: https://aistudio.google.com/docs/models/gemini-decision-1
- Google blog launch post: https://blog.google/innovation-and-ai/technology/developers-tools/gemini-decisions-api
- Artificial Analysis Decision Index entry: https://artificialanalysis.ai/decision-models/gemini-decision-1
- TimescaleDB real-time aggregates: https://docs.timescale.com/use-timescale/latest/continuous-aggregates/real-time-aggregates
