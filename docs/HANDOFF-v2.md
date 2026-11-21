# Hack Western 13 handoff v2: AI Robot Redesign Engine

Updated Sat Nov 21, 2026. Devpost deadline: **Sun Nov 22, 9am EST**.

**What changed from v1:** we no longer just recommend US-made replacement parts. We **find a replacement, check that it works, and regenerate the robot's CAD to fit it.** The sourcing and compliance work from v1 becomes step 1 ("why this part has to go").

**Still valid in [HANDOFF.md](HANDOFF.md) (v1):** policy facts and sources (§2), prize rules and how to compete for each track (§3, §3a), TinyFish limits (§4), rejected ideas (§8). [ARCHITECTURE.md](ARCHITECTURE.md) describes the v1 design. Where it disagrees with this file, this file wins.

---

## 1. The pitch

> "This robot's drive motor has to be replaced to meet US sourcing rules. Finding another motor is easy. The hard part is knowing it actually works and changing the robot to fit it. Our AI engineer does both, live."

**Hackathon scope:** a small wheeled robot. **One subsystem, the drive motor and its mounting bracket**, is redesigned end to end. Then we generate 2–3 competing designs (lowest cost, best performance, US-first).

**Full product vision (pitch only, don't build):** upload any CAD assembly and BOM, redesign every affected subsystem, run simulation, and export for engineering review.

---

## 2. Simplifications (locked, don't reopen)

1. **NEMA-standard motors only (NEMA 17 / 23 / 34).** The frame size fixes the bolt pattern, pilot diameter and shaft diameter. The agent only has to find **frame size, body length, torque, speed and voltage**, which are usually plain text on the page. Bolt patterns come from our lookup table (§6), not from Gemini reading drawings.
2. **We build the whole robot ourselves in CadQuery:** base plate, wheels, motor mounts, electronics box. Don't import GrabCAD models (painful to convert, license restrictions, not parametric). Clean and labelled is better than realistic.
3. **Parametric template, not general CAD editing.** The bracket is a function `bracket(frame, body_len, clearance)`. Be upfront about this in the pitch.
4. **One subsystem.** We show the whole robot, but only the motor mount changes.
5. **Four checks, all in code:** torque, speed, voltage and fit (§6). "Pass" means "passes the checks we implemented", and the UI says so.

---

## 3. Fixes from review (build these into the design)

1. **Magnets are a supply risk, not a compliance hit.** My understanding of the Buy American Act component test (confirm with counsel before saying it on stage): a component is domestic if *it* is made in the US, whatever its sub-parts (except iron and steel). A US-made motor with Chinese NdFeB magnets still counts as domestic. **Show two separate tracks:** "Compliance: 67% ✅" and "Supply risk: magnets ⚠️". Never mix them.
2. **US final assembly is required too.** A robot is a "domestic end product" only if it is **manufactured in the US** *and* more than 65% of its component cost is domestic. If the demo robot is Canadian-built, the verdict must say "also needs US final assembly." Canadian parts count as foreign.
3. **Every swap gets a fit badge:** `drop_in` / `close` / `needs_review`, with a spec comparison table (for example "torque 0.28 vs 0.30 Nm (−7%)"). The code checks decide pass or fail. Gemini only writes the explanation.
4. **Concurrency fallback for the live tiles.** A standard account gets about 2 Agent runs at a time. Ask the TinyFish booth for an increase first thing. If we don't get it: run TinyBrowser sessions (5) plus cached replays, and say in the pitch which tiles are live.
5. **Build order.** Core first, in this order: **robot CAD + bracket generator → agents find real motors → checks → regenerated bracket in the viewer.** Nothing else until that works end to end.

---

## 4. Making the TinyFish part strong

TinyFish judges on: **a real job done start to finish, agents that hold up on live websites, smart use of TinyFish, and a demo that makes them want to hire it.** The CAD step is what the job *produces*. It doesn't replace the job. Present it like a job description:

> **Role:** Sourcing engineer. **Each run:** searches US motor manufacturers and distributors, reads product pages and datasheets, verifies origin and price from the source, and delivers specs that the CAD engine can build from.

| Step | TinyFish product | What it does |
|---|---|---|
| Discovery | **TinySearch** + **TinyFetch** (free within limits) | Broad search across manufacturers and distributors for NEMA motors that meet the requirements. Cheap, so cast a wide net. |
| Deep extraction | **TinyAgent** (`/run-batch`, `/run-sse`) | Opens product pages, finds the datasheet, and returns the `output_schema` below. **Shows `streaming_url` tiles live on screen.** |
| Verification | **TinyFetch** (`html`) | Fetches the source page again and checks in code that `origin_quote`, the price and the frame size appear word for word. |
| Quote flow | **TinyBrowser** + Playwright | Fills one supplier's RFQ or quote form and **stops before submitting**. That's the end-to-end "job done." |
| Watching | **TinyMonitor** | Watches the chosen motor's page for price or stock changes. Events go to Tiger Data. |

**Rules that make it hold up:**
- Every result carries `status` + `reason`. `COMPLETED` does not mean success.
- Data fields are optional, so unreachable fields don't get placeholder values.
- Use `max_duration_seconds` (GA) as the run limit. `max_steps` needs beta access.
- No CAPTCHA solving: mark the site `blocked` and move on. Test target sites in hour one.
- One honest identity on real sites. No fake personas.
- **Log every run to Tiger Data** (§8), then show a "success rate by site" panel. That's evidence the agents hold up on live websites, not just a claim.
- Pre-identify 2–3 real NEMA motors that the swarm is known to find, so the demo can't come up empty.

**`output_schema` for the agent:**

```json
{
  "status": "success | blocked | not_found | auth_required | incomplete",
  "reason": "string",
  "manufacturer": "string?",
  "part_number": "string?",
  "nema_frame": "string? (17 | 23 | 34)",
  "body_length_mm": "number?",
  "rated_torque_nm": "number?",
  "rated_speed_rpm": "number?",
  "voltage_v": "number?",
  "shaft_diameter_mm": "number?",
  "price_usd": "number?",
  "lead_time_days": "number?",
  "country_of_origin": "string?",
  "origin_quote": "string? (exact text from the page)",
  "product_url": "string?",
  "datasheet_url": "string?"
}
```

**Social post (required for eligibility):** post the demo clip on X or LinkedIn and tag TinyFish.

---

## 5. Pipeline: who does what

| # | Step | Done by |
|---|---|---|
| 1 | Load the robot (parametric CadQuery model + BOM + requirements) | Code |
| 2 | Compliance card: coverage check, domestic %, US-assembly requirement, magnet supply-risk flag | Code |
| 3 | Plan the search: requirements → queries + target sites | Gemini |
| 4 | Discovery + extraction | TinyFish |
| 5 | Read datasheet PDFs where the page lacks specs | Gemini (multimodal, strict JSON) |
| 6 | Verify origin, price and frame size against the page HTML | Code |
| 7 | Engineering checks: torque, speed, voltage, fit | Code |
| 8 | Tournament: choose the best candidate by cost / performance / US-first | Code |
| 9 | Regenerate the bracket + assembly, export GLB | Code (CadQuery) |
| 10 | Explanations, comparison write-up, RFQ draft | Gemini (numbers passed in, no math) |

**Hard rules:** the LLM never does arithmetic. Every number links to its source. Unverified candidates never reach the checks. "Not legal advice / not engineering certification" stays visible in the UI.

---

## 6. Engineering checks (code)

Inputs from the robot's spec: mass `m`, wheel radius `r`, number of drive motors `n`, gear ratio `G`, drivetrain efficiency `η`, rolling resistance `Crr`, maximum slope `θ`, target acceleration `a`, top speed `v_max`, bus voltage `V_bus`, safety factor `SF` (about 1.5).

| Check | Pass if |
|---|---|
| Torque | `r·m·(g·(Crr·cosθ + sinθ) + a) / (n·G·η) · SF ≤ rated_torque_nm` |
| Speed | `(rated_speed_rpm / G) · 2πr / 60 ≥ v_max` |
| Voltage | `voltage_v` matches `V_bus` (or is within the driver's supported range) |
| Fit | `body_length_mm + bracket thickness + clearance ≤ chassis envelope`, and `nema_frame` is in the lookup table |

Result per candidate: **Rejected** (fails torque, speed or voltage), **Review** (fits only with changes, or data is missing), **Pass\*** (meets every check we implemented).

**NEMA lookup table.** These are typical values. **Check each one against a real vendor drawing before building**, because shaft size varies by model.

| Frame | Bolt-hole spacing (square) | Pilot diameter | Common shaft diameter |
|---|---|---|---|
| NEMA 17 | 31.0 mm | 22.0 mm | 5 mm |
| NEMA 23 | 47.14 mm | 38.1 mm | 6.35 mm or 8 mm |
| NEMA 34 | 69.6 mm | 73.0 mm | 9.5 / 12.7 / 14 mm |

---

## 7. CAD engine

- **CadQuery** (Python). Functions: `robot(params)`, `motor(frame, body_len)`, `bracket(frame, body_len, clearance)`.
- The bracket uses the bolt spacing and pilot diameter from the NEMA table, its width comes from the frame size, and its depth and position move with `body_len`.
- Export the assembly to **GLB** (glTF) for the browser, and to **STEP** as the "engineering export".
- Viewer: **`<model-viewer>`** or **three.js** with a **before/after slider**, the changed bracket highlighted, and the three tournament designs as tabs.
- **Start this first.** It's the least familiar piece and the biggest moment in the demo.

---

## 8. Sponsor technology: how each one is used

### TinyFish (core prize)
See §4. Search/Fetch for discovery, Agent for extraction with live tiles, Fetch HTML for verification, Browser for the RFQ form, Monitor for price and stock changes.

### Gemini (MLH Best Use of Gemini)
- **Multimodal datasheet reading:** send PDFs or images of spec tables directly and get back **strict JSON** that matches our motor schema.
- **Long context:** compare 3–5 candidate datasheets side by side in one call and produce the spec comparison text.
- **Search planning:** robot requirements → search queries + target sites for TinyFish.
- **Writing:** fit explanations ("why Motor B needs review"), the design comparison write-up, and the RFQ draft.
- **Deliberately not used for:** arithmetic, pass/fail decisions, origin verification. Say this in the Devpost write-up.

### Vultr (MLH Best Use of Vultr)
- **Backend on Vultr compute:** orchestrator API (FastAPI) + workers. Put CadQuery (OCCT dependencies) in a Docker image on the Vultr VM so nobody fights local installs.
- **Tournament in parallel:** each design variant is a worker job (checks + CAD regeneration + GLB export) running at the same time.
- **Vultr Object Storage** (S3-compatible): generated GLB/STEP files, downloaded datasheets, and captured HTML evidence for the verifier.
- Show the architecture diagram in the demo and name Vultr.

### Tiger Data (MLH Best Use of Tiger Data)
Real time-series use, not just tables:
- **`agent_runs`** (hypertable): `time, run_id, site, product, status, duration_s, steps`. Continuous aggregate **`site_success_hourly`** powers the "success rate by site" panel. That panel doubles as TinyFish evidence.
- **`price_observations`** (hypertable): `time, part_number, supplier, price_usd, lead_time_days, origin, run_id`. Filled by repeated runs and TinyMonitor events.
- **`check_results`** (hypertable): `time, design_id, candidate, check, value, threshold, pass`. This is the audit trail behind each Pass/Review/Rejected.
- **`design_variants`** (regular table, same database): design ID, objective, cost, domestic %, GLB URL. Relational and time-series data side by side is Tiger Data's pitch.
- Name the hypertables and continuous aggregates in the Devpost write-up.

### Also cheap to add (details in v1 §3a)
- **Auth0:** a manager approves before the RFQ is submitted.
- **Entire:** one Trail per feature plus session handoffs (see [ENTIRE.md](ENTIRE.md)).
- **GoDaddy:** a live domain hosting the demo.

---

## 9. Demo script (3 minutes)

1. **The problem (20 s):** the robot in 3D. "This drive motor has to go: here's the compliance card." It shows 38% domestic, needs US final assembly, and a separate magnet supply-risk flag.
2. **Find and Redesign (60 s):** click. Live TinyFish tiles search manufacturers and distributors, and verified results pop in (✅ / ⚠️ blocked / ❌ not found).
3. **Engineering checks (30 s):** the table shows Motor A Rejected (torque), Motor B Review (fit), Motor C Pass\*. Each number links to its source.
4. **The key moment (40 s):** the bracket regenerates. Before/after slider: the bracket widens and the holes move. STEP export button.
5. **Tournament (20 s):** three tabs (lowest cost / best performance / US-first), each with its cost, domestic %, and 3D model.
6. **Close (10 s):** RFQ drafted and waiting for approval. "From 'this part has to go' to a buildable design in 3 minutes."

---

## 10. Team split

| Owner | Area |
|---|---|
| 1 | **CAD:** parametric robot + bracket in CadQuery, GLB/STEP export, 3D viewer with before/after |
| 2 | **Agents:** TinyFish discovery/extraction/verification, Gemini datasheet extraction, run logging |
| 3 | **Engineering + data:** checks, NEMA table, demo robot requirements, compliance card, 2–3 pre-identified real motors, Tiger Data schema |
| 4 | **Frontend + infra + demo:** UI flow, live tiles, comparison view, Vultr deployment, domain, video, social post |

## 11. Milestones

- [ ] **Now:** TinyFish booth (concurrency increase, beta access for `max_steps`, file upload). Ask the organizers about prize stacking. Test target sites for bot walls.
- [ ] **Sat 2pm:** a bracket regenerates from hard-coded motor specs and shows up in the viewer.
- [ ] **Sat 6pm:** the swarm returns verified specs for at least 2 real motors. The checks give Pass/Review/Rejected.
- [ ] **Sat 10pm:** end to end: click → agents → checks → regenerated bracket. Deployed on Vultr.
- [ ] **Sun 2am:** tournament (3 variants), Tiger Data panels, RFQ draft.
- [ ] **Sun 4am: FEATURE FREEZE.** 4–8am: pre-run and cache demo inputs, record a backup video, write the Devpost page, post the social clip.

## 12. What to cut if we're behind (cut first at the top)

1. Auth0 approval → show the RFQ as a draft only
2. TinyMonitor → static price history
3. Tournament → one redesign only
4. TinyBrowser quote form → link to the supplier's quote page
5. Tiger Data panels → a basic table (Tiger Data keeps logging in the background)

**Never cut:** live agents finding real motors, code-based checks, the regenerated bracket in the viewer.
