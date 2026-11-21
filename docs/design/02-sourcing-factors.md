# 02 What a robot company must weigh when buying parts (US market, as of Nov 21, 2026)

Not legal advice. Every rate depends on the exact HTS code and country of origin of the part;
check the current Chapter 99 notes before relying on a number here.

## A. Market access (can we sell the robot at all?)

1. FCC Covered List, robots (July 28, 2026). New ground-mobile robot models must be a "domestic
   end product": made in the US AND domestic component cost > 65% (2024-2028), > 75% (2029+).
   Allied parts count as foreign; COTS parts count; unknown origin = foreign. Duty and freight
   are part of a foreign part's component cost, so duties also LOWER your domestic %.
   Escape hatch: DoW Conditional Approval, applications close Jan 1, 2028.
2. FCC 26-50 (effective Oct 13, 2026): no authorization for devices containing logic-bearing
   hardware (chips, modules, smart-battery BMS) from entity-listed producers such as Huawei,
   ZTE, Hikvision, Dahua, regardless of percentage.
3. Prong 1 is binary: a robot assembled outside the US fails at any percentage. "Manufactured"
   is undefined in the FAR, so screwdriver assembly is a counsel question.
4. "Made in USA" marketing is a separate, stricter FTC standard ("all or virtually all").

## B. Landed cost: the tariff stack on each imported part

Duties stack. For a given part, add the layers that apply:
1. Base HTS rate (often 0-4% for electronics and motors).
2. Section 301 China, technology-transfer lists: 25% (Lists 1-3) or 7.5% (List 4A). Four-year
   review raised strategic lines: semiconductors 50% (from Jan 1, 2025), non-EV lithium-ion
   batteries 25% and permanent magnets 25% (both from Jan 1, 2026).
3. Section 301 forced-labor action (since July 24, 2026): +12.5% on China and most economies,
   +10% on 17 (incl. Canada, Mexico, UK, India). USMCA-qualifying goods and Section 232 goods
   are exempt. This replaced the Section 122 10% surcharge, which replaced the IEEPA tariffs
   the Supreme Court struck down on Feb 20, 2026.
   Example: Chinese non-EV Li-ion pack = 3.4% + 25% + 12.5%.
   Example: Chinese-origin MCU pays 50% Section 301; a Malaysian-origin one pays 0.
4. Section 232 metals (rebuilt Apr 6, 2026, on full customs value): steel/aluminum/most copper
   articles 50%; listed derivatives 25%, or 15% for some partners; 10% if the metal is >= 85%
   US melted/smelted; 0% if under 15% metal by weight outside Ch. 72-76. Hits frames,
   extrusions, fasteners, wire and cable (copper cable must report smelt/cast country).
5. Section 232 machinery: handling robots (8428.70) and machining centers pay 15% total through
   Dec 31, 2027, then the 25% derivative rate. Robots under 8479.50 pay none today.
6. Section 232 semiconductors (Jan 15, 2026): 25%, but only for narrow AI-accelerator
   performance bands, and civil industrial/robotics use and startups are exempt. Rarely bites.
7. Section 232 drones (Sept 3, 2026): only drone aircraft, docks and 8807 drone parts; motors,
   batteries and cameras under their own codes are not listed. Watch if you share parts with
   drones.
8. De minimis: the $800 duty-free exemption is suspended, so small prototype orders from
   overseas pay full duty.
9. Upside: IEEPA duties paid in 2025-26 are refundable through CBP's CAPE process
   ($137.9B in claims by Oct 23, 2026). Worth checking your past entries.

## C. Supply security (can we keep getting it?)

1. Rare earths. China Announcement 18 (Apr 2025) still requires a per-order export licence for
   NdFeB magnets containing terbium or dysprosium (the high-temperature SH/UH/EH grades); MOFCOM
   has 45 working days and can refuse. The broader Oct 2025 package (incl. a rule reaching
   foreign-made products containing Chinese rare earths) is suspended only until Jan 10, 2027.
   MOFCOM has said finished rotors/stators with fixed magnets generally fall outside
   Announcement 18, so buying a finished motor is less exposed than buying magnets.
   China's 2024 ban on gallium/germanium/antimony exports to the US is suspended only to
   Nov 27, 2026.
2. Forced labor (UFLPA). Goods with any Xinjiang input or from Entity List companies (190 as
   of Oct 29, 2026) are presumed barred; the importer must rebut with "clear and convincing"
   evidence. High-priority sectors include lithium, aluminum, copper, steel, PVC, polysilicon:
   batteries, frames, motors and cable. FY2025: ~7,325 shipments stopped, ~6.5% released.
3. Entity and military lists. DoD 1260H list (June 2026) added Unitree, Hesai, RoboSense, CALB,
   EVE Energy, BOE, TP-Link and others; mainly a defense-customer and reputational risk. BIS
   "Affiliates Rule" (50%-owned subsidiaries of listed entities) is suspended to Jan 10, 2027.
4. Domestic capacity is thin for reducers, frameless motors, magnets and lidar; expect
   qualification backlogs and price premiums (Sustainment, Sept 2026).

## D. Policy volatility (dated watchlist)

- Jan 10, 2027: China rare-earth suspension and BIS Affiliates Rule suspension both lapse
  unless extended.
- Apr 26, 2027: Section 232 robotics/industrial machinery negotiation update due (Proclamation
  11077, Oct 28, 2026, found a national-security threat but imposed no tariff yet).
- May 24 / Jun 23, 2027: Section 301 Chinese legacy-chip tariff rises from 0% to a rate to be
  announced (on top of the existing 50%).
- Dec 31, 2027: 15% machinery tier ends.
- Jan 1, 2028: Conditional Approval window closes.
- Jan 1, 2029: 75% threshold; firmware-update waiver runs at least to here.
- Canada-US: USMCA not renewed on Jul 1, 2026 (stays in force, annual reviews); Canada broke
  off talks Aug 22, counter-tariffs on ~C$27.6B of US goods (incl. electronics) since Sep 8;
  US Section 338 duties and import bans on some Canadian vehicles, dairy, alcohol. A Canadian
  company importing US parts into Canada may pay Canadian counter-tariffs.

## E. Ordinary commercial factors (still decide most purchases)

Unit price and price breaks, MOQ, lead time and stock depth, freight and brokerage, FX
(CAD/USD), payment terms, NRE/tooling for custom parts, qualification and first-article time,
second source availability, lifecycle/EOL risk, authorized channel vs broker (counterfeits),
warranty/support, shipping certifications (UN38.3 for batteries), and now: whether the
supplier will sign a country-of-origin declaration.

## Reading list

Start here (about 45 min):
1. Sentinel Automata, "Will your robot pass the FCC's 65% test?" - clearest worked example.
   https://automata.llc/blog/fcc-covered-list-robots-65-percent-test/
2. Sidley, FCC robotics listing analysis - authoritative legal framing.
   https://www.sidley.com/en/insights/newsupdates/2026/08/fcc-adds-all-foreign-produced-advanced-robotic-devices-to-the-covered-list
3. HTSBase, Section 301 China tariffs in 2026 - the tariff stack in one page.
   https://htsbase.com/blog/section-301-china-tariffs-2026
4. Mainrich, which magnets need a Chinese export licence (Nov 2026).
   https://www.mainrichinternational.com/resources/articles/china-rare-earth-export-controls-2026-ndfeb-mofcom-licensing
5. Sustainment, "A new standard for building American in robotics" - practical sourcing view.
   https://www.sustainment.com/post/an-emerging-standard-for-building-american

Compliance (primary and near-primary):
- FCC Covered List: https://www.fcc.gov/supplychain/coveredlist
- FCC FAQ robots/inverters (quoted by several sources, not yet opened by us):
  https://www.fcc.gov/covered-list-faqs-robots-inverters
- 48 CFR 25.101: https://www.ecfr.gov/current/title-48/chapter-1/subchapter-D/part-25/subpart-25.1/section-25.101
- Gatewell, how a product qualifies (component cost rules):
  https://gatewellgroup.com/domestic-end-product-fcc-covered-list
- Gatewell Protocol for Origin Evidence v1.0 (evidence file + BOM schema):
  https://gatewellgroup.com/protocol/v1.0/
- Lotus International, subassembly strategy and FCC 26-50:
  https://licus.com/the-fcc-redrew-the-map-for-robots-and-inverters-in-america-heres-how-to-stay-on-it/
- Crowell, Aug 20 update (AGVs in scope):
  https://www.crowell.com/en/insights/client-alerts/fcc-clarifies-covered-list-for-power-inverters-and-advanced-robotic-devices

Tariffs:
- ABA, IEEPA struck down and Section 122 expired:
  https://www.americanbar.org/groups/public_contract_law/resources/procurement-lawyer/2026-fall/ieepa-tariffs-struck-down-replacement-tariffs-expired/
- Strix, Section 232 metals tiers: https://strixsmart.com/resources/blog/section-232-derivatives-50-percent
- GingerControl, Section 232 robotics proclamation and what machinery pays now:
  https://gingercontrol.com/blog/section-232-robotics-industrial-machinery-tariff
- Findchips, semiconductor tariffs for BOM pricing: https://blog.findchips.com/semiconductor-tariffs-2026/
- Lithium-ion battery tariff layers: https://www.large-battery.com/blog/us-tariff-on-chinese-lithium-ion-batteries/
- USTR legacy-chip Section 301 notice: https://www.federalregister.gov/documents/2025/12/29/2025-23912/notice-of-action-chinas-acts-policies-and-practices-related-to-targeting-of-the-semiconductor

Supply security and politics:
- China Announcement 58 of 2026 tracker: https://strategic-materials-policy-tracker.vercel.app/events/china-rare-earth-suspension-extension-2026-11
- Daptic, UFLPA explained: https://www.daptic.com/resource/uflpa/
- Troutman, UFLPA and lithium-ion: https://www.troutman.com/insights/high-voltage-enforcement-uflpa-turns-up-the-heat-on-lithium-ion-and-energy-storage-imports
- DoD 1260H list, June 2026: https://www.federalregister.gov/documents/full_text/html/2026/06/10/2026-11571.html
- Dechert, Affiliates Rule pause: https://www.dechert.com/knowledge/onpoint/2026/11/a-reprieve--not-a-repeal--bis-extends-the-affiliates-rule-pause.html
- Blakes, US-Canada tariff timeline: https://www.blakes.com/insights/us-canada-tariffs-timeline-of-key-dates-and-documents
- ICPA USMCA review tracker: https://www.icpainc.org/usmca-joint-review-tracker-home
- YC RFS, Robots Made in America: https://www.ycombinator.com/rfs#robots-made-in-america
