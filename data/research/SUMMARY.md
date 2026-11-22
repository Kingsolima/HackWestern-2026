# Research summary: demo BOM, tariffs, lists, NEMA (checked 2026-11-21)

Drafts for owner 3 and Tygo. Every number in the YAML files has a source URL, a verbatim quote
and a date. Values without a source are `null` with a note. Not legal advice.

## Files

- `data/research/demo_bom.yaml`: 12 BOM lines plus the US motor swap, with price, origin, tier, HTS guess and supply risk.
- `data/research/tariffs.yaml`: duty layers per HTS code and origin, plus the Bank of Canada CAD/USD rate.
- `data/research/nema_drawings.yaml`: NEMA 17/23/34 from vendor drawings, and a list of where they differ from the code tables.
- `data/lists/fcc_covered_list.yaml`, `dod_1260h.yaml`, `uflpa_entity_list.yaml`, `README.md` (answers the covered-device question).

## Key findings

1. **The baseline motor is real.** STEPPERONLINE iSV57T-090S is a NEMA 23 integrated servo:
   "Rated Torque(Nm/oz.in): 0.3/42.49", "Peak Torque(Nm/oz.in): 0.8/113.29", 20-50 VDC, $77.15
   at qty 1, ships from China. Its origin evidence is only company-wide (T3, CN). It has an
   integrated drive, so the v2 "motor driver" line goes away.
2. **The Teknic swap is stronger than HANDOFF-v3 said.** The CPM-SDSK-2310S-RLN model page states
   "Country of Origin USA", so T1, not T2. Price $265 at qty 1 (JS page, read with a browser).
   Continuous torque 45 oz-in (0.318 N*m) at 75 VDC. Torque at 24 V still needs the curve.
3. **The swap alone does not get the priced lines past 65%.** These are simple sums of the
   priced lines in demo_bom.yaml, before freight and duty:
   - Baseline: 2 x 77.15 + 110.00 + 99.00 + 189.99 + 44.95 + 2 x 9.99 + 4.49 = **$622.71**.
     Domestic (T1/T2 and US) = Pololu regulator **$44.95**.
   - After the swap: 2 x 265.00 + 110.00 + 99.00 + 189.99 + 44.95 + 2 x 9.99 + 4.49 = **$998.41**.
     Domestic = 530.00 + 44.95 = **$574.95**.
   - 65% of $998.41 is $648.97, which is **$74.02 more** than $574.95. Duties on the lidar (and
     on the battery if it is Chinese) only add to the foreign side, so the gap is larger once
     tariffs are in.
   So the honest stage story is: the motor swap is the biggest single move but not enough;
   the engine has to find a second line. Code should compute the final percentages.
4. **Next cheapest line to move: the battery.** It is the largest foreign or unknown line left
   ($189.99, Bioenno BLF-2410AS, origin not stated anywhere we looked, so it counts as foreign).
   With the Teknic swap in, swapping the battery for any battery with T1/T2 US evidence, at any
   price p, passes on the priced lines: 574.95 + p > 0.65 x (808.42 + p) holds for every p >= 0.
   (808.42 is 998.41 minus 189.99.) We did **not** find a sourced US-made 24 V pack yet. Leads
   from the search results (not verified, no price): Advance Energy Inc. says "Each of our
   battery pack is designed. assembled, and rigorously tested in our Las Vegas facility"
   (https://advanceenergyinc.com, search snippet only); docs/design/01 lists Inventus, MaxAmps and Emerging Power.
   Also cheap, as a $0 lever: ask Bioenno where the BLF-2410AS is assembled. Unknown origin
   counts as foreign, so proving origin can move the number without a swap.
   The other big foreign lines have no US source found: Raspberry Pi 5 ($110, GB) and RPLIDAR
   A1M8 ($99, CN). The deck (SendCutSend, US, T2) helps but has no price yet; to close the gap
   on its own it would need to cost more than about $211, which a small laser-cut plate will not.
5. **The robot is plausibly a covered device.** The FCC FAQ definition (ground locomotion,
   operates from commands or sensor data, over 4.4 lb, has a perception sensor, a network link
   of at least 200 kbps and navigation software) fits our 5 kg lidar robot with a Pi 5. With
   final assembly in Canada it fails prong 1 at any percentage. Details and open points:
   `data/lists/README.md`.
6. **Tariff stack as of Nov 21, 2026** (all checked against the HTS Rev. 23 Chapter 99 PDF and
   the USTR forced-labor notice):
   - IEEPA tariffs: struck down Feb 20, 2026. Section 122 surcharge: expired July 24, 2026.
   - Section 301 forced-labor duty since July 24, 2026: CN 12.5% (9903.05.31), GB/MY/CA 10%,
     TW topped up to 10% total with MFN, JP topped up to 12.5% total.
   - **8471.50.01 (Raspberry Pi) is exempt** from the forced-labor duty (USTR Annex II Part A,
     no scope limit). With GB origin the Pi pays no US duty at all.
   - Motor 8501.31.40: MFN 4% + List 2 25% + 12.5% if Chinese.
   - Lidar 9031.80.80 (guess): MFN Free + List 1 25% + 12.5% if Chinese.
   - Battery 8507.60.00: MFN 3.4% + four-year review 25% (9903.91.06) + 12.5% if Chinese.
   - Section 232 metals: 50% on aluminum articles like 7616.99.51, 25% on some derivatives; and
     232 goods are exempt from the forced-labor duty.
   - CAD/USD = 0.6981 (Bank of Canada, Nov 20, 2026).
7. **NEMA tables need one real fix for the demo.** The Teknic NEMA 23 ships with a 3/8 in
   (9.525 mm) shaft by default; neither code table lists 9.525 (backend has 6.35 and 8; CAD has
   6.35). The baseline iSV57T has 8 mm. Also the Teknic flange is 59.10 mm, not 57.2, and its
   holes are 5.20 mm, not 5.1. Bolt circle and pilot agree. See `nema_drawings.yaml`.

## Unknown or unsure

- **Battery origin** (none found) and a US-made battery with a price: the main gap.
- **Raspberry Pi 5 origin conflicts.** Two European distributors say GB per SKU; an Amazon.de
  listing says China; an Indian reseller says Japan (search snippets). If a lot is Chinese it
  pays 25% (List 3).
- **Lidar HTS code** is a guess (9031.80.80 vs 9015.80.80). Both are List 1, so the China duty
  is the same either way.
- **NEMA 17 values** come from a search snippet of an Oriental Motor drawing; the pilot is not
  sourced. Drawing dimension labels for NEMA 23/34 were inferred from the layout.
- **Prices that may move:** the Pi 5 price rose three times in 2026 (DRAM). The Bioenno pack and
  the Pololu D36V50F5 were out of stock or rationed on Nov 21. The StepperOnline price is the
  ship-from-China price; the US warehouse adds $12.58.
- **Not sourced at all:** wheel hubs, wiring harness, fasteners, deck price. They are `null`.
- **Teknic torque at 24 V** (page shows 75 VDC values).
- **FCC 26-50** (logic-bearing hardware rule) was not re-opened; no BOM vendor matched the
  Covered List, 1260H or UFLPA names in a string search.
- **UFLPA count:** we parsed 210 table rows (newest Oct 29, 2026); docs/design/02 says 190.
  Not reconciled.
- **Section 301 China list membership** was found by text search of Chapter 99 notes, not by a
  broker. 10-digit carve-outs were not checked. Exclusions lapsed Nov 9, 2026 (htsbase).

## What changes the demo story

- Before: the swap was expected to cross 65%. Now: the swap goes from $44.95 domestic of $622.71
  to $574.95 of $998.41 (pre-duty sums), short of 65% by $74.02. The demo should show the engine
  then picking the battery as the next line (prove origin or swap), which is a better story about
  per-line evidence than a single motor swap.
- The Teknic evidence is T1 from its own model page: a clean verifier demo.
- Integrated baseline motor: no driver line, and the fit_shaft check changes (8 mm to 9.525 mm).
