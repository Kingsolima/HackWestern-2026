# Devpost submission draft (Hack Western 13)

Deadline: Sun Nov 22, 2026, 9am EST. Draft pulled from HANDOFF.md, HANDOFF-v2.md, HANDOFF-v3.md,
BUILD-PLAN-v4.md, DEMO-COMPANY.md, ENTIRE.md and the code on `ui/bombot`. Every claim below is
backed by code in the repo; section 4 lists what was planned but not built, so it stays out of
the write-up. Items marked TODO need a human.

## 1. Submission checklist

- [ ] Project name and tagline (section 2)
- [ ] Demo video link (TODO: URL). Backup video recorded during the freeze.
- [ ] Live site link (TODO: GoDaddy domain, or the Vultr IP if DNS is not up; docs/DEPLOY.md)
- [ ] Repo link: https://github.com/Kingsolima/HackWestern-2026 (public, so Entire transcripts
      are visible to judges; check `entire checkpoint list --outgoing` for secrets first)
- [ ] Prize tracks selected on Devpost (section 5)
- [ ] TinyFish gate: demo clip posted on X or LinkedIn, tagging TinyFish (TODO: post URL)
- [ ] Screenshots: mission-control console, risk table + recommendations, live agent tiles,
      3D before/after of the J2 mount, success-by-site panel, Entire Trail pages
- [ ] Entire proof (ENTIRE.md): `entire checkpoint list`, `entire activity`, `entire dispatch`,
      `entire trail show`, Trail screenshots from entire.com
- [ ] Team members added on Devpost (TODO)
- [ ] Ask organizers whether one team can win more than one MLH prize (still open)

## 2. Name and tagline

Name: BOMbot (repo name: AI Robot Redesign Engine)

Tagline options:
- "Tell it who you are and what's in your robot. It tells you which parts will hurt you, finds
  real replacements on live sites, and redesigns the mount to fit."
- "Supply-chain risk for robotics teams, from parts list to a regenerated part."

## 3. Write-up

### Inspiration

Most robots built in North America are full of imported motors, magnets and drives. China made
94% of sintered rare-earth magnets in 2024, and its April 2025 export limits forced production
cuts at automakers. YC's "Robots Made in America" request lists motors, magnets, gears, encoders
and battery packs as gaps. US federal buyers add their own rules (65% domestic content, FCC
covered list, entity lists). But the risk that matters depends on who you are: a startup selling
to US federal labs and a student club importing into Canada should care about different parts.

Finding another part is easy. Knowing it is real, knowing it works in your robot, and changing
the robot to fit it is the hard part. We built a tool that does all three.

### What it does

1. Onboarding: a team describes itself in plain language (who they are, who buys, where it
   runs, budget, deadline, what to avoid) and uploads a parts list. Gemini turns the answers
   into facts; numbers come from the BOM and CAD, not the model. Company facts can be verified
   live against the company's own pages.
2. Criteria: code rules turn those facts into objectives and blocking lists. Selling to US
   federal buyers switches on domestic content and the restricted lists; deploying in Canada
   uses Canadian duty (CBSA 2026 tariff); a need-by date makes lead time a hard limit.
3. Risk priority for every BOM line: priority = supply + customer + impact, each 0-3 with the
   evidence it was read from. Unknown is never scored as zero: missing evidence on an
   important part leads to "investigate", not "keep".
4. Deep dive on the most important part (the actuator): TinyFish agents search manufacturers
   and distributors for real replacement motors, a code verifier re-fetches each page and
   confirms the quote and number, and code checks torque, speed, voltage and fit against the
   joint requirement computed from the arm's geometry.
5. Recommendation per line: keep, dual-source or re-source, ranked by risk reduction and cost.
6. CAD: CadQuery regenerates the motor mount for the chosen motor and shows before/after in a
   3D viewer (GLB in the browser, STEP for engineers).

Demo cases (same engine, opposite priorities):
- Northfield Robotics (made-up company, real robot): an Annin AR4 six-axis arm, 60-line parts
  list read from Annin's 37-page BOM PDF. Sells to US federal labs, assembles in Canada, needs
  parts in 30 days, wants to avoid Chinese rare-earth magnets. Result: all 60 lines scored,
  J5 motor first (45-day lead time beats the 30-day need-by), the other China-made motors next
  (41.5% added US duty, likely rare-earth dependent), and Teknic CPM-SDSK-2331S-RLN (US) found
  live as the best J2 candidate.
- Boston Dynamics Stretch (company facts verified live from bostondynamics.com; BOM and
  shoulder actuator are ILLUSTRATIVE and labelled as such).
- A Western robotics club AR4 build (stated facts, real public parts).

Honesty in the UI: illustrative data is badged ILLUSTRATIVE, stated facts are badged "stated by
the team", inferred risks are shown as inferred, and "Pass*" means "passes the checks we
implemented", not engineering certification. Not legal advice.

### How we built it

The core rule: code owns the control flow, and no LLM produces a number, a verdict, a risk
level or an origin tier. An LLM may extract a fact with a quote; the verifier confirms the
quote; code applies the rules.

- Orchestrator (FastAPI, asyncio): a code state machine with stages INTAKE, CRITERIA,
  RISK_BASELINE, PLAN, DISCOVER, TRIAGE, EXTRACT, VERIFY, CHECK, RANK, ALTERNATIVES, RECOMMEND,
  BUILD, REPORT. Workers are code loops, not LLM agents. The UI is a pure function of the SSE
  event log.
- TinyFish:
  - TinySearch + TinyFetch (free) cast the wide net for discovery and read every lead as
    markdown, 10 URLs per call.
  - Gemini Decision 1 plus code rules triage each page: readable pages go to Fetch + Gemini
    Flash extraction; only pages that need clicking get a TinyAgent run.
  - TinyAgent via /run-sse with a strict output schema (status + reason on every result,
    because COMPLETED is not the same as success; data fields optional so the agent never
    invents placeholders). Live streaming_url tiles in the UI.
  - When a site blocks the agent, one retry with the stealth browser profile and a US proxy.
  - The verifier re-fetches with ttl=0 and string-matches the quote and the number. For values
    a page fills in with JavaScript (Teknic torque), it uses the agent's own page snapshot of
    the same canonical URL, labelled agent_dom.
  - One bad agent result no longer fails the job: each run's outcome is classified
    (success, blocked, not_found, auth_required, incomplete, error).
- Gemini: Decision 1 for routing choices with calibrated probabilities; 2.5 Flash for JSON
  extraction with quotes (onboarding answers, product pages, company pages); never for
  arithmetic, pass/fail, risk levels or origin tiers.
- Engineering: units table in code; torque/speed/voltage/fit checks; an arm-joint requirement
  (holding torque from payload and link masses at full reach, plus inertia times acceleration,
  through the gearbox) for the AR4 J2 shoulder; NEMA lookup table for bolt patterns so no LLM
  reads drawings.
- Tiger Data (TimescaleDB): hypertables `agent_runs`, `board` (the blackboard workers share;
  only the verifier writes facts), `price_observations` and `check_results`; continuous
  aggregate `site_success_hourly` powers the "success rate by site" panel, which is evidence
  the agents hold up on live websites; relational `design_variants` in the same database.
- CAD: CadQuery worker in its own Docker image renders the AR4 with Annin's real link meshes
  around a generated J2 drive and mount, exports GLB + STEP, and returns generic fit-check rows
  the backend turns into checks.
- Record/replay wraps every TinyFish and Gemini call from hour one (82 agent, 28 fetch, 9
  search and 49 Gemini recordings in the repo), so the full demo replays offline with a
  LIVE/REPLAY badge. Live jobs need a token because they spend credit.
- Vultr: one Toronto VM runs the stack with Docker Compose; Caddy serves the site and proxies
  /api and /cad; the CAD image (about 2 GB) builds on the server.
- Frontend: Vite + React + TypeScript mission-control console.
- 276 backend tests; ruff + oxlint.

### Challenges we ran into

- COMPLETED is not success: agent runs often "complete" with all-null data or a CAPTCHA page.
  We classify every run in code.
- DigiKey (Cloudflare) and Mouser (Akamai) block plain headless browsers; stealth + US proxy
  retry helped, and blocked sites are marked and skipped instead of stalling the job.
- Some spec values (Teknic torque) only exist after JavaScript runs, so a plain re-fetch could
  not verify them; we added a verify method that uses the agent's own snapshot of the same URL.
- "Designed in USA" is not "made in USA": origin tiers come from code rules over verified
  quotes, and an LLM can only lower a tier, never raise it.
- The problem itself changed overnight: from "replace a motor to hit 65% domestic content" to
  "work out which supply risks this team cannot tolerate". Domestic content became one rule
  that a fact switches on.

### Accomplishments that we're proud of

- Real agents on real vendor sites, with every number traceable to a quote on its source page.
- Unknown is never treated as safe.
- The same engine gives opposite answers to a US-federal-facing company and a Canadian club.
- The robot's CAD actually changes to fit the part the agents found.

### What we learned

TODO: one or two lines per teammate.

### What's next

- RFQ drafting with a human approval step before anything is sent (Auth0 for AI Agents).
- TinyMonitor on chosen parts to track price and stock over time into Tiger Data.
- Alternatives for every line, not just the deep one, so more lines reach re-source or
  dual-source.
- Upload any CAD assembly instead of parametric templates.

### Built with

python, fastapi, asyncio, pydantic, tinyfish, gemini, timescaledb, tiger-data, postgresql,
cadquery, docker, caddy, vultr, react, typescript, vite, three.js,
godaddy (TODO: if the domain is live), entire

## 4. Planned but not built: do not claim

- Auth0 approval and the RFQ flow: `backend/app/agents/rfq.py` raises NotImplementedError;
  Auth0 is only config fields.
- TinyBrowser quote form and TinyMonitor: not in the code.
- Vultr Object Storage: `backend/app/db/storage.py` is a client stub, unused.
- Advocates / synthesizer / critic (HANDOFF-v3 section 1): not built.
- Tournament of three designs (lowest cost / best performance / US-first): check the UI
  before claiming it.

## 5. Prize tracks

Tracks (from HANDOFF.md section 3). Name the specific features in the write-up, not a token
integration.

- TinyFish "Hire Your First AI Employee" (main target). Judged on: real job done start to
  finish, holds up on live websites, smart use of TinyFish, a demo that makes them want to hire
  it. Pitch it as a job description: "Role: sourcing engineer. Each run searches manufacturers
  and distributors, reads product pages, verifies origin and price from the source, and
  delivers specs the CAD engine can build from." Point at: Search/Fetch for the cheap wide net,
  Agent only where clicking is needed, stealth + proxy retry, status classification, the
  success-by-site panel. Gate: social post tagging TinyFish.
- MLH Best Use of Gemini: Decision 1 for routing, Flash for quoted JSON extraction, and the
  explicit list of what Gemini is deliberately not used for.
- MLH Best Use of Tiger Data: name the hypertables (`agent_runs`, `board`,
  `price_observations`, `check_results`) and the continuous aggregate (`site_success_hourly`),
  and the relational `design_variants` table next to them.
- MLH Best Use of Vultr: the whole stack, including the CadQuery worker, runs on a Vultr VM.
  Show the architecture diagram (docs/design/architecture.html).
- Entire: Trails per feature, overnight session handoffs between teammates, proof commands
  from ENTIRE.md. TODO: token-savings numbers if measured.
- GoDaddy: only if the domain is live with the demo on it.
- Organizers' Choice "Most Adventurous" (theme "Discover the unknown"): unknown is never
  scored as safe; the engine goes looking.
- Do not show any sponsor negatively (DoorDash sponsors Hack Western).

## 6. Demo video outline (3 minutes)

TODO: adapt to the final UI. Based on HANDOFF-v2 section 9 and DEMO-COMPANY.md.

1. Problem (20 s): Northfield Robotics, AR4 arm, sells to US federal labs, assembled in
   Canada, parts in 30 days, no Chinese rare-earth magnets.
2. Onboarding (20 s): paste the answers, upload the BOM, review screen with stated facts and
   the J2 joint numbers.
3. Risk map (30 s): 60 lines, J5 blocked by lead time, five China-made motors next, magnets as
   a stated conflict, US-made parts kept.
4. Live agents (50 s): tiles searching vendor sites, verified quotes popping in, blocked sites
   marked, checks giving Review / Rejected / Pass*.
5. Key moment (40 s): J2 mount regenerates in 3D, before/after, STEP export.
6. Close (20 s): ranked recommendations; same engine on Stretch gives different priorities.
