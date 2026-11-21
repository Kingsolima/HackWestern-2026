# 01 Feasibility test (Sat Nov 21, 2026, ~2am EST)

Verdict: GO, with a reframe. The legal premise is real, current and tighter than the handoff
assumed. The calculator is a commodity; the unserved, TinyFish-shaped job is per-line ORIGIN
EVIDENCE: prove where each part is made, find verified US-made swaps, and hand over a file that
backs the FCC certification.

## 1. Premise check (verified against sources)

- FCC Covered List page (dated Nov 18, 2026) lists "Foreign-produced advanced robotic devices,
  except ... Conditional Approval by DoW", added July 28, 2026.
  https://www.fcc.gov/supplychain/coveredlist
- "Foreign-produced" = not a domestic end product under 48 CFR 25.101(a): manufactured in the US
  AND domestic component cost > 65% (2024-2028), > 75% (2029+). Must EXCEED, 65.0% fails.
  https://www.ecfr.gov/current/title-48/chapter-1/subchapter-D/part-25/subpart-25.1/section-25.101
- RESOLVED (was "open question"): the COTS waiver does NOT apply. FCC FAQ for robots/inverters
  says the COTS exception is "inapplicable" and "all components, including COTS components, must
  be considered" (fcc.gov/covered-list-faqs-robots-inverters, quoted by Gatewell, Sentinel
  Automata, PrephysicalAI). Note: some law-firm alerts (Morgan Lewis, MoFo) still say COTS is
  waived; the FCC FAQ governs.
- Allied content does not count (BAA, not DFARS). Canadian/Japanese/German parts = foreign.
  Producer nationality is irrelevant ("country neutral").
- Math rules from 48 CFR 25.003:
  - Denominator = component cost: purchased part at acquisition cost incl. freight to the line
    and duty; self-made part at manufacturing cost + overhead, no profit. Final assembly,
    labor, design and test of the robot are excluded from both sides.
  - ONE LEVEL DOWN: each direct component is domestic or foreign as a whole by where it was
    manufactured. Magnets inside a US-made motor do not count against you.
  - Unknown origin = foreign.
- Evidence: applicant certifies under 47 CFR 2.911(d)(5); FAQ says "sufficient evidence" needed,
  "no specific documentation or evidence required". Nobody has defined what a good file is.
- Extra hard stop (FCC 26-50, effective Oct 13, 2026): devices containing logic-bearing
  hardware from entity-listed producers (Huawei, ZTE, Hikvision, Dahua, ...) are barred
  regardless of the percentage.
- Open, flag for counsel (do not assert): "manufactured" is undefined in the FAR, so whether
  final assembly alone (or "screwdriver" subassembly) meets prong 1 is unsettled; how the 2029
  75% step maps onto models authorized before 2029 is unstated in the FAQ.

## 2. Changes to the handoff

1. Lead with evidence, not the calculator. Free calculators already exist (Netray, OpenTree).
2. New phase before swaps: VERIFY CURRENT PARTS. Unknown origin counts as foreign, so proving
   that a part you already buy is US-made raises the score at $0. Often the cheapest lever.
3. Swap types, not just "buy a US part":
   a. US-made catalog equivalent (motors, encoders, drives, bearings, gears).
   b. US-manufactured subassembly (PCBA from a US assembler, battery pack assembled in the US,
      wire harness, machined/sheet-metal frame). This is where real US capacity exists.
      Counsel flag: substantial manufacture vs screwdriver assembly is fact-specific.
   c. Leave foreign and say so: compute modules, lidar, cameras, radios usually have no
      verified US source. Reporting "none found" honestly is a feature.
4. Magnets move OUT of the compliance math (one level down) and INTO the risk/disclosure
   section: Conditional Approval guidance asks for supply-chain concentration by country (% of
   value and volume) and a sole-source register with contingency plans.
5. Evidence quality tiers, enforced by the verifier:
   - T1: distributor COO field for that exact part (e.g. Mouser shows Country of Origin /
     Assembly / Diffusion per SKU) or a manufacturer product page naming the plant.
   - T2: manufacturer site states that product line is made at a named US facility.
   - T3: company HQ in the US only. NOT evidence of origin.
   - Reject: "Designed in USA", "NDAA-compliant", "US company", distributor address.
6. Outputs aligned to an existing structure: Gatewell Protocol for Origin Evidence v1.0
   (CC BY 4.0) Annex B.1 BOM schema (mpn, component_mfr, coo, supply_channel, sole_source,
   deep_trace) + concentration summary + sole-source register, and the CA guidance items.
7. Entity check: flag BOM lines from entity-listed producers (hard stop, deterministic list).
8. Prong 1 is binary and outside the BOM: a robot assembled in Canada fails at any %. The
   report must state "assumes final assembly moves to the US".
9. Prices: many US industrial suppliers are "request a quote". Never invent a price: missing
   price = "quote required" -> draft RFQ, and the optimizer only uses sourced prices or a
   user-entered estimate labelled as such.

## 3. Prior art (closest first)

- OpenTree / Sentinel Automata (opentree.shop): curated non-Chinese robot parts catalog, US
  component map (40 pinned makers, origin claims "unverified", "most of the map is empty"),
  in-browser 65% worksheet. Sells its own joints (conflict of interest). Static, not per-BOM.
- Sustainment: US manufacturer discovery. Bloom ($3.6M seed, Oct 2026): AI matching of
  robotics/drone builders to domestic contract suppliers, quoting. Mackiba: one RFQ to US shops.
- Gatewell Group: evidence protocol + consulting. Fresh Consulting: BOM mapping services.
  Law firms: Sidley, Steptoe, Squire, White & Case, Morgan Lewis, MoFo, K&L Gates, Crowell.
- Gap none of them close: take MY BOM, verify each line's origin live with captured evidence,
  find verified swaps, compute the cheapest path, emit the evidence file + RFQs.

## 4. Technical feasibility evidence (what was actually tested)

- Teknic ClearPath page loads with plain fetch and states "build and ship it to you from our
  New York manufacturing plant" (T2 evidence on the product page).
- US Digital product page loads in a headless browser but does not state origin; origin lives
  on company pages -> multi-page agent job (good TinyFish fit).
- DigiKey: Cloudflare "Just a moment" to headless browser. Mouser: "Access denied" (Akamai).
  Not yet tested through TinyFish stealth (no key yet). TinyFish self-reports up to 85% pass on
  strict sites, no CAPTCHA solving.
- US suppliers exist per category (company-stated, unverified): motors/drives (Teknic NY,
  Allient NY, ElectroCraft OH, maxon Taunton MA, Moog Animatics NC), encoders (US Digital WA,
  Encoder Products ID), gears (Harmonic Drive LLC MA, Cone Drive MI), magnets (Noveon TX, MP
  Materials TX, Vulcan NC), battery packs (Inventus IL, MaxAmps, Emerging Power NJ), force
  sensors (FUTEK CA). Sources: opentree map via jaredwatkins.com summary; uxvmarket.com.

## 5. Risks and mitigations

- Bot walls on big distributors -> start from manufacturer sites (often unprotected), use
  TinySearch/TinyFetch for discovery, stealth profile + US proxy for Mouser, cache demo runs.
- COMPLETED != success -> status + reason fields in every output_schema; verifier re-fetches.
- 2 concurrent agent runs on standard accounts -> ask booth for bump; design the wall to look
  good with 2-5 live tiles plus queued cards.
- ~31h left -> one deep vertical (wheeled AMR, ~12 lines), cut negotiation entirely.

## 6. Hour-one tests (need TinyFish key)

1. TinyAgent on a Mouser SKU page, stealth + US proxy: does it return the COO fields?
2. Same for DigiKey. 3. TinyAgent multi-page origin hunt on usdigital.com.
4. TinySearch "made in USA" + part category: are results usable for discovery?
