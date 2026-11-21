# Hack Western 13 handoff: Robot supply-chain navigator (TinyFish)

Session date: Fri Nov 20, 2026 (EST). Hacking: Fri Nov 20, 9pm to Sun Nov 22, 9am EST (Devpost deadline 9am Sun).
Team: Tygo (tyfifago) + teammates (Omar Soliman in thread), up to 4 people. Venue: Western University, London ON.
Load the `hackathon-ideation` skill first (references/sponsor-notes.md has distilled facts below plus more).

## 1. Current decision (where we landed)

Build a **robot supply-chain navigator** for the **TinyFish "Hire Your First AI Employee"** prize.
Spirit: paradigm shifts in robotics and how robotics companies navigate turbulent times (YC RFS "Robots Made in America").

Input: a robot BOM (part, cost, origin if known). Output: is the robot FCC-covered, domestic-content %, verified US-made swaps found live by a web-agent swarm, cheapest path to the 65% / 75% thresholds, hidden-dependency flags (rare-earth magnets), dated policy timeline, draft RFQs.

The "AI employee" job = sourcing + compliance engineer, done end to end on live supplier websites.

## 2. Why (key facts, all sourced)

- FCC Covered List, July 28, 2026 (Public Notice DA 26-786): new models of "foreign-produced advanced robotic devices" cannot get FCC equipment authorization, so cannot be imported/marketed/sold in the US.
  - Covered device: ground-mobile (AMR, humanoid, quadruped, wheeled/tracked), operates at a distance from a human, >4.4 lb incl. dock, has a perception sensor + connectivity >=200 kbps + autonomy/command software.
  - Excluded: fixed arms (SCARA, gantry, articulated industrial/medical), drones, connected vehicles, rail, underwater, FDA medical devices.
  - "Foreign-produced" = not a "domestic end product" under 48 CFR 25.101(a) (Buy American Act): manufactured in US AND domestic component cost >65% (through 2028), >75% (2029+).
  - Allied content does NOT count (BAA, not DFARS). Canadian parts = foreign.
  - Escape route: DoW Conditional Approval, applications due Jan 1, 2028; needs supply-chain disclosures + US manufacturing plan.
  - Already-authorized models unaffected; firmware-update waiver through at least Jan 1, 2029.
  - Sources:
    - https://www.sidley.com/en/insights/newsupdates/2026/08/fcc-adds-all-foreign-produced-advanced-robotic-devices-to-the-covered-list
    - https://www.steptoe.com/en/news-publications/global-trade-and-investment-law-blog/fcc-adds-advanced-robotic-devices-to-the-covered-list.html
    - https://www.squirepattonboggs.com/insights/publications/fcc-adds-foreign-produced-power-inverters-and-advanced-robotic-devices-to-the-covered-list/
    - https://www.whitecase.com/insight-alert/us-federal-communications-commission-prohibits-new-foreign-made-power-inverters-and
  - OPEN QUESTION (do not assert): whether the COTS prong of 48 CFR 25.101(a) applies. Law-firm summaries do not mention it. Show as "flag for counsel".
- YC RFS "Robots Made in America" (Diana Hu): https://www.ycombinator.com/rfs#robots-made-in-america
  - US installed 38,400 industrial robots in 2025 (+12%), mostly imported (Japan/Europe).
  - China made 94% of sintered rare-earth magnets (2024); April 2025 export restrictions forced some automaker production cuts.
  - YC wants US supply chain for: rare-earth magnets, motors, strain-wave gears, encoders, force sensors, grippers, chips, battery packs.
- Trade context (Nov 2026): Section 232 robotics/industrial machinery investigation closed with no tariffs for now, 180-day negotiation, remedies possible later; US 232 tariffs on Canadian steel/autos/lumber set to rise 25% to 50% in Jan; Section 338 list on Canadian goods modified Oct 30; USTR Section 301 overcapacity recs due end of 2026.
  - https://natlawreview.com/article/tariff-ied-week-international-trade-november-2-2026

## 3. Prize rules (Hack Western 13 Devpost, read in browser)

- **TinyFish: Hire Your First AI Employee** - $75 gift card + $100 TinyFish credits per member + 1:1 with a TinyFish engineering lead. Judged on: a real job done start to finish, agent holds up on live websites, smart use of TinyFish, demo that makes them want to hire it. **Gate: post the demo on X or LinkedIn and tag TinyFish.** Credits: tinyfish.ai/students. Docs: docs.tinyfish.ai.
- Other possibly stackable (UNVERIFIED stacking, ask organizers): Organizers' Choice "Most Adventurous" (theme "Discover the unknown"), MLH Best Use of Gemini (if Gemini is the LLM), MLH Best Use of Vultr, Auth0, Tiger Data, Entire, GoDaddy, Best Hardware Prototype by PCBWay (unlikely), overall placements. How to compete for each one: section 3a.
- Sponsor caution: DoorDash sponsors Hack Western; never show a sponsor negatively.

## 3a. Competing for the other tracks

Each sponsor wants to see what makes its product special, not a token integration. Name the specific features in the Devpost write-up.

- **Gemini.** Use more than text in, text out:
  - Multimodal: read datasheet PDFs, product photos and spec tables directly (swarm step 4, verifier step 5).
  - Structured output: strict JSON schemas for extracted part specs.
  - Long context: compare long datasheets side by side.
  - Say exactly where Gemini does what, and where it is deliberately not used: all arithmetic stays deterministic (calculator, optimizer).
- **Vultr.** Do more than host a web page:
  - Run the swarm orchestrator and verifier workers on Vultr compute.
  - Show it scaling for a big BOM.
  - Mention it in the demo with an architecture diagram.
- **Auth0.** Use Auth0 for AI Agents, not just a login button:
  - The agent asks a human to approve before any RFQ is sent (fits "draft RFQs, stop before send" in step 8).
  - Permissions limit what the agent can do on the user's behalf.
  - Roles: an engineer drafts, a manager approves.
- **Tiger Data.** Make real time-series use of it, not just a regular table:
  - Hypertables for supplier price and lead-time history from repeated agent runs.
  - Policy and monitor events on a timeline (step 7, TinyMonitor).
  - A live dashboard powered by continuous aggregates, for example "domestic % over time as swaps are approved".
  - Name hypertables and continuous aggregates in the Devpost write-up.
- **Entire.** Commands are in [ENTIRE.md](ENTIRE.md).
  - Measure token savings: compare agents using Entire graph search against blind file search, with real numbers.
  - Hand sessions between teammates (overnight handoffs are ideal).
  - Store key decisions in Brain, for example "never let the LLM do arithmetic".
  - Use Trails for agent code review.
  - Screenshot all of it for the Devpost page.
- **GoDaddy.** Register a short, clever, memorable domain that is actually live, with the demo running on it.

## 4. TinyFish technical notes (from docs, Nov 2026)

- Products: TinyAgent (goal -> actions, $0.016/step; /run sync, /run-async, /run-batch up to 100, /run-sse with live `streaming_url`), TinyBrowser (CDP session, $0.002/min, drive with Playwright), TinySearch + TinyFetch (free within limits), TinyMonitor (page/topic change + LLM judge), TinyResearch, Vault + TinyProfiles (saved logins, cookies persist across runs).
- Proxies: US, GB, CA, DE, FR, JP, AU. `browser_profile`: lite | stealth.
- **Limits/gaps to design around:**
  - Standard accounts: ~2 concurrent Agent runs, 5 Browser sessions. ASK THE BOOTH FOR A HACKATHON BUMP EARLY.
  - `COMPLETED` != goal met. Errors often only in `result` text; `error.code` only on sync /run. Put `status` (success|auth_required|blocked|incomplete) + `reason` in `output_schema`. Required unreachable fields get placeholders, so keep data fields optional.
  - No CAPTCHA solving. `max_steps` is beta-gated (403 without beta, enroll at agent.tinyfish.ai/beta); `max_duration_seconds` is GA.
  - Screenshots/snapshots not shipped; `html` capture is available (use it for evidence + verifier string-match).
  - File upload support in TinyAgent unknown: use TinyBrowser + Playwright `setInputFiles` for instant-quote sites.
- Design rule: broad discovery with TinySearch/TinyFetch; reserve Agent runs for datasheets, quote flows, carts.

## 5. Architecture sketch

1. BOM ingest (CSV): part, category, qty, unit cost, supplier, known origin.
2. Coverage checker: deterministic checklist against the 4 prongs + exclusions, with rule citations.
3. Domestic-content calculator: deterministic; unknown origin = foreign (safe default). Show 65% and 75% lines.
4. Swap-finder swarm (TinyFish): per foreign/unknown part, find US-made alternatives; extract price, lead time, stated country of origin, datasheet URL.
5. Verifier agent: re-fetch source page/html and string-match the origin claim + price; assign status; reject unverified.
6. Optimizer: choose the swap set that crosses 65% (and plan to 75%) at minimum added cost per robot (small knapsack/ILP; deterministic).
7. Risk + timeline: hidden dependencies (NdFeB magnets in motors), dated events with sources; TinyMonitor on FCC/USTR/Federal Register pages.
8. Outputs: compliance gap report, verified supplier shortlist, draft RFQs (stop before send), Conditional Approval disclosure outline.
9. Optional (cut first): negotiation strategies (volume buyer, fast payer, flexible lead time) under ONE honest identity ("AI buyer acting for &lt;team&gt;"), ideally against a mock supplier agent. Do not run fake personas against real vendors.

Rules: never let an LLM do arithmetic; every number links to a source; "not legal advice" in UI.

## 6. Demo (3 min)

1. Upload BOM of a small mobile robot (ideally a real Canadian team's robot).
2. Verdict: "Covered device. 38% domestic. Cannot launch a new model in the US." Note Canadian parts count as foreign.
3. Wall of live TinyFish browser tiles hunting US-made swaps; verified sources pop in.
4. Money shot: "Swap these 4 parts -> 67% domestic for +$412/robot. Still exposed: magnets (China 94%). 2029 plan to 75%."
5. Hand-off: draft RFQs + disclosure outline. Post clip on X/LinkedIn tagging TinyFish.

## 7. Immediate next steps

- [ ] Ask TinyFish booth: concurrency bump, beta access (max_steps), whether Agent supports file upload.
- [ ] Ask organizers: prize stacking (TinyFish + Gemini, Vultr, Auth0, Tiger Data, Entire, GoDaddy). See section 3a.
- [ ] Register the GoDaddy domain early so DNS is live before the demo.
- [ ] Record Entire token-savings numbers (graph search vs blind file search) as you go, not at the end.
- [ ] Build demo BOM: 10-12 real parts with prices + known origins; for the 3-4 highest-cost parts, pre-identify 2-3 real US-made alternatives so the swarm is known to succeed.
- [ ] Hour-one tests: target supplier/distributor sites (DigiKey, Mouser, RobotShop, Thomasnet, manufacturer sites) for bot walls and whether origin is stated.
- [ ] Freeze features ~4am Sun; 4-8am: pre-run and cache demo inputs, record backup video, write Devpost page.

Suggested split: (1) calculators + optimizer + coverage checker, (2) TinyFish swarm + verifier + monitors, (3) data: BOM, supplier targets, policy timeline, (4) frontend wall/report + demo video + social post.

## 8. Ideas considered and rejected (do not re-litigate without new info)

- QNX prize ideas (safety guard, GPU rack watchdog, agent-swarm-on-RTOS): pivoted away from QNX. Research verdict: RTOS matters for agents only when sharing a box with physical control loops, not for web/cloud swarms.
- Generic "true cost of anything" arbitrage: too broad; LLM invents line items.
- Manufacturing true-cost (aluminum, tariffs): team not excited; competitors TariffRadar, SenseAhead, Chainomics, Quickcode, Deepbeez, Navo.
- GPU rent/buy true cost: rental comparison saturated (gpu.compare, gpu.info, gpufinder, gputape free API, etc.).
- Drip-pricing Checkout X-ray, "money you are owed", Nowcast inflation, Parallel Lives (7 persona swarm across country proxies), agent-vs-agent bazaar: judged boring or kept as fallbacks. Site-to-API and persona QA swarms already startups (Writ, Pomerado, ApiTap, Unbrowse; Swarm, Composal YC, Synthetic Users).
- Intermediate robotics sourcing idea (instant-quote swarm on SendCutSend/Xometry/JLCPCB/PCBWay + timing research + negotiation) is absorbed into section 5 as features.
