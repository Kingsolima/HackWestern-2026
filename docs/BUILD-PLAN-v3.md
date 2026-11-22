# Build plan v3: Tygo's track (owner 2)

Written Sat Nov 21, 2026, ~5:15pm EST, from `docs/HANDOFF-v3.md`, `docs/design/04/05/07` and
the code on `origin/main` (PR #1, PR #2, both by Omar). HANDOFF-v3 still wins where they disagree.
Status: APPROVED ("go with your assumptions", ~5:30pm). Chunk 1 scaffold is on `tygo/core-scaffold`.

## 1. Playback

Build the middle of the system: a code-owned orchestrator that fans out workers, calls TinyFish
and Gemini through one record/replay client, lets only a code Verifier promote raw claims to
facts, runs owner 3's checks and ranking, asks Omar's CAD worker for the bracket, and streams
everything to Omar's UI as SSE events. No LLM produces a number, verdict or origin tier.
Never cut: live agents on real sites, verifier, code checks, regenerated bracket.

## 2. Ground rules for Omar's areas (CAD + frontend)

Omar wrote `cad/`, `frontend/`, `db/schema.sql`, `docker-compose.yml` and the backend scaffold.
He is actively working on CAD and frontend design, so:

- No edits under `cad/` or `frontend/` from this track. Anything we need there goes to Omar as
  an ask (section 6), not a commit.
- Existing endpoints keep their exact shapes until Omar opts in: `/health`, `/api/robot`,
  `/api/compliance`, `/api/candidates/seed`, `POST /api/checks`, `/api/designs`.
  `frontend/src/types.ts` mirrors `schemas.py`, so schema changes are additive only (new
  models, new fields with defaults). The flat `MotorCandidate` stays until one coordinated PR.
- New routes live under `/api` (his router prefix and his Vite proxy already cover it):
  `POST /api/jobs`, `GET /api/jobs/{id}`, `GET /api/jobs/{id}/events`,
  `GET /api/designs/{id}/glb`, `GET /api/designs/{id}/step`.
- CAD is consumed only over his HTTP API, as-is: `POST {CAD_WORKER_URL}/build
  {design_id, frame, body_len, clearance}` -> `{glb, step}` paths. The backend never imports
  CadQuery. `/api/designs/{id}/glb` redirects to whatever URL his worker returns, so his
  planned switch to Vultr Object Storage needs no backend change.
- `db/schema.sql` deltas (owner 2 per handoff) are additive and announced to him first; his
  local TimescaleDB volume must be recreated (`docker compose down -v`) to pick them up.
- Unblock him early: a replayable demo job on `/api/jobs` by ~7:30pm so he can build tiles,
  compliance card and design tabs from the event log instead of placeholders.

## 3. Chunks and schedule (EST)

Each chunk is one branch, one Entire Trail, one PR, hands-on flow (playback, design checkpoint,
Tygo writes the core, verify, report card, teach-back, decision log).

| # | Window | Chunk | Done means | Core for Tygo |
|---|---|---|---|---|
| 0 | 5:20-5:35 | Setup | branch, Py 3.12 venv under /home/pn, `make test` + `make lint` green | - |
| 1 | 5:35-7:30 | Scaffold: schema deltas, events + SSE, tfclient record/replay, verifier, orchestrator skeleton with fake workers | fake job streams every stage over SSE; recorder round-trips; verifier tests fail only on the two stubs | `classify_outcome`, `verify_claim` |
| 2 | 7:30-8:45 | Live TinyFish: Search, Fetch (`ttl=0`), Agent `/run-sse` with our schema, streaming URL event | one live Teknic run recorded; Verifier confirms >= 1 quote from a fresh fetch; same run replays offline | retry/outcome policy in the fleet |
| 3 | 8:45-11:00 | Motor job end to end: PLAN, DISCOVER, TRIAGE, EXTRACT, VERIFY, CHECK, RANK, BUILD | one job: discover -> GLB in Omar's viewer, tiles live, deployed on Vultr (with Omar) | triage routing rule |
| 4 | 11:00-1:30 | Tiger Data board + tasks + agent_runs, 2 origin workers, circuit breaker, supply math | facts only via Verifier (DB constraint), breaker opens on 2 blocks, compliance card from `domestic_share()` | circuit breaker state machine |
| 5 | 1:30-3:30 | Synthesis: case builder, advocates round 1, synthesizer, RFQ draft | validated advocate JSON in `advocate` events; report numbers rendered by code | advocate validator |
| - | 3:30-4:00 | If time: cross-exam, Decision 1 critic, gap round | - | - |
| - | 4:00-8:00 | FREEZE: record replay fixtures, backup video, Devpost | full demo job replays offline | - |

The 8pm milestone (live run + verified quote) lands ~8:45: chunk 2 starts while Tygo writes the
chunk 1 core. Cut order if behind is the handoff's (section 6); never cut the four items above.

Dependencies on others: owner 3 ports `checks.py` to Claims + units (chunk 3 consumes it; until
then an adapter feeds the current flat checks), `tournament.py` and the demo BOM; Omar owns the
viewer, tiles and Vultr deploy.

## 4. Chunk 1 design (for approval)

### Files

```
backend/app/
  schemas.py            + Spec, AgentMotorCandidate, Source, Claim, OriginEvidence, Candidate,
                          RunRecord, Outcome, Event; BomRow + origin_tier, freight_usd,
                          duty_usd, hts_code (all defaulted). Existing models untouched.
  tfclient/
    recorder.py         Recorder: key = sha256(product + canonical request); store = gzip JSON
                        under data/recordings/<product>/<key>.json.gz; modes live|replay|mixed
    client.py           TFClient.search / fetch / agent_run (async iterator of AgentEvent) /
                        get_run; GeminiClient.generate_json / decide. Every call goes through
                        Recorder and returns live: bool. httpx only, no SDK for TinyFish.
  agents/verifier.py    classify_outcome (CORE), verify_claim (CORE), origin_tier (agent-written)
  orchestrator/
    events.py           EventLog per job: append, subscribe(from_id), JSONL file per job
    job.py              Stage enum + transitions; run_job(job, deps) drives stages
    fleet.py            per-product semaphores, per-domain lock, per-job budgets (skeleton)
    workers.py          SwapWorker / OriginWorker protocol; FakeSwapWorker for now
  api/jobs.py           POST /api/jobs, GET /api/jobs/{id}, GET /api/jobs/{id}/events (SSE)
backend/tests/
  test_verifier.py      failing tests for the two core functions + origin tier tests
  test_recorder.py, test_events.py, test_jobs_api.py
```

### Data shapes (new, from 04 section 4; abbreviated)

```python
Outcome = Literal["success", "blocked", "not_found", "auth_required", "incomplete", "error"]

class AgentRunResult(BaseModel):     # what classify_outcome reads
    run_id: str; tf_status: Literal["PENDING","RUNNING","COMPLETED","FAILED","CANCELLED"]
    result: dict | None              # parsed output_schema JSON, if any
    error: str | None; page_text: str | None; steps: int | None; duration_s: float

class Claim(BaseModel):
    id: str; candidate_id: str; field: str
    raw_value: str; raw_unit: str | None; quote: str
    source: Source; si_value: float | None = None
    extracted_by: Literal["tinyagent", "gemini_text", "gemini_vision"]
    verified: bool = False
    verify_method: Literal["html_quote", "pdf_text", "none"] = "none"

class Event(BaseModel):              # every SSE message
    id: int; type: EventType; job_id: str; ts: datetime; data: dict
```

### Signatures

```python
def classify_outcome(run: AgentRunResult) -> Outcome                 # Tygo
def verify_claim(claim: Claim, text: str, method: VerifyMethod) -> Claim  # Tygo, returns a copy
def origin_tier(statement_class: OriginClass, quote_on_model_page: bool) -> Tier

class Recorder:
    async def call(self, product: str, request: dict,
                   live_fn: Callable[[], Awaitable[dict]]) -> tuple[dict, bool]
    async def stream(self, product: str, request: dict,
                     live_fn: Callable[[], AsyncIterator[dict]]) -> AsyncIterator[tuple[dict, bool]]

class EventLog:
    def emit(self, type: EventType, data: dict) -> Event
    async def subscribe(self, after_id: int = 0) -> AsyncIterator[Event]
```

### Diagram

```
 Omar's UI ──POST /api/jobs──► api/jobs.py ──spawn──► orchestrator/job.py (stage loop)
     ▲                                                   │        │
     └──── SSE /api/jobs/{id}/events ◄── EventLog ◄──────┘        ▼
                                                          workers.py (fake now)
                                                                  │
                                         tfclient/client.py ◄─────┘
                                                  │
                                         tfclient/recorder.py ──► data/recordings/*.json.gz
                                                  │ live
                                          TinyFish / Gemini
          raw claims ──► agents/verifier.py ──► facts ──► checks (owner 3) ──► CAD /build (Omar)
```

### Tests left failing for Tygo (handoff section 7)

- COMPLETED run whose result is all nulls -> `incomplete`, not `success`.
- COMPLETED with `status != success` in the result -> that status.
- page text with "access denied" / CAPTCHA -> `blocked`; FAILED -> `error`.
- quote present but number differs (promo vs regular price) -> not verified.
- quote split across tags (`<b>425</b> oz-in`) -> verified after normalization.
- whitespace and thousands commas normalized on both sides.
- "Designed in USA" never yields T1/T2 (origin_tier, agent-written, passes from the start).

## 5. Verification per chunk

`make test`, `make lint` (ruff check + format; frontend lint untouched), a mutation pass over the
verifier rules, and the CI workflow on the PR. Live-only steps (chunk 2+) are proven by a
recorded fixture that a test replays offline.

## 6. Asks for Omar (send before chunk 1 ends)

1. OK with `/api/jobs*` under the existing `/api` prefix (handoff wrote `/jobs`)?
2. Event catalog (`stage`, `run_started`, `run_streaming_url`, `run_progress`, `run_finished`,
   `claim_verified`, `claim_rejected`, `check_result`, `compliance`, `design_ready`,
   `advocate`, `synthesis`, `error`): payload shapes live in `backend/app/orchestrator/events.py`
   (one model per type); he mirrors them in `types.ts` when ready. `POST /api/jobs
   {"mode": "replay"}` runs a fake job today (labelled `fake`, `live: false`).
3. Replay tiles: a recorded run has no live browser behind its `streaming_url`. Proposal: tile
   shows the REPLAY badge and the recorded step log instead of the iframe.
4. Bracket thickness lives twice (`cad_worker/robot.py BRACKET_T`, `checks.py
   BRACKET_THICKNESS_MM`); he and owner 3 pick one owner (e.g. CAD worker exposes its params).
5. When he wants the v3 `MotorCandidate`/`CheckResult` shapes in the UI, we do one coordinated
   PR (backend + `types.ts`) and drop the legacy shapes.

## 7. Decisions for Tygo (recommendation first)

1. Base branch: branch `tygo/core-scaffold` from `design/v3` and open a docs-only PR
   `design/v3 -> main` now. Alt: branch from `origin/main` (loses the schemas and specs chunk 1
   tests read).
2. Schema delta: additive `AgentMotorCandidate` next to the legacy flat `MotorCandidate`, which
   is removed in one later PR with Omar. Alt: replace in place and edit `types.ts` (touches his
   frontend mid-design).
3. SSE: FastAPI's own `fastapi.sse.EventSourceResponse` (ships in 0.165, so still no new
   dependency) with `Last-Event-ID` resume. Alt: `sse-starlette`.
4. Recordings: gzip JSON files committed under `data/recordings/` (demo survives offline and
   in CI). Alt: Vultr Object Storage (needs network on stage).
5. Board in chunk 1: in-memory `Board` behind the same interface Tiger implements in chunk 4.
   Alt: Tiger from the start (blocks tests on Tiger Cloud setup).
6. PR gate: CI (`make test`, `make lint`) + Entire Trail review agents, which is the team flow
   in `docs/ENTIRE.md`. Alt: full lverify gate with the Gemini reviewer sign-off per PR (adds a
   review round per chunk; nothing lverify-related may land in this shared repo either way).
