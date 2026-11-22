# data/lists: restricted-entity and covered-equipment lists

Checked 2026-11-21. Drafts for the compliance code; not legal advice.

| File | List | Official source | List date |
|---|---|---|---|
| `fcc_covered_list.yaml` | FCC Covered List (47 CFR 1.50002) | https://www.fcc.gov/supplychain/coveredlist | page dated "(November 18, 2026)" |
| `dod_1260h.yaml` | DoD Section 1260H "Chinese military companies" | https://www.federalregister.gov/documents/full_text/html/2026/06/10/2026-11571.html (91 FR 35189) | published June 10, 2026 |
| `uflpa_entity_list.yaml` | DHS UFLPA Entity List | https://www.dhs.gov/uflpa-entity-list | newest entry effective October 29, 2026 |

The 1260H and UFLPA names were split out of the source pages by a script. Check the counts
against the source before you quote a number on stage (see `parse_notes` in each file).
None of our BOM vendors (StepperOnline, Slamtec, Raspberry Pi, Bioenno, Pololu, goBILDA,
SendCutSend, Teknic) matched a name on the 1260H or UFLPA lists in a plain string search.

## What "covered" means for the robot rule (HANDOFF-v3 section 9 question)

**The rule.** On July 28, 2026 the FCC added "Foreign-produced advanced robotic devices, except
advanced robotic devices which have been granted a Conditional Approval by DoW" to the Covered
List. Covered equipment "is prohibited from getting FCC equipment authorization", and new
foreign-produced devices are "generally prohibited from receiving FCC authorization to be
imported, marketed, or sold in the U.S." Models that already have an authorization, and devices
people already own, are not affected. Source: FCC FAQ, https://www.fcc.gov/covered-list-faqs-robots-inverters.

**"Foreign-produced"** means anything that is not a "domestic end product" under 48 CFR
25.101(a). That test has two prongs: the device must be "manufactured in the United States",
and "the cost of domestic components shall exceed 65 percent for items delivered in calendar
years 2024 through 2028 and 75 percent for items delivered starting in calendar year 2029."
The FAQ adds that the COTS exception is "inapplicable" (same FAQ page).

**"Advanced robotic device"** (FAQ, quoting the National Security Determination) is a
"mechanical mobile device, including autonomous mobile robots, humanoid robots, and quadrupeds,
that" meets all of these:

| Test (FAQ wording) | Our demo robot | Plausibly met? |
|---|---|---|
| (i) "Is capable of locomotion, obstacle avoidance, navigation, or movement on the ground" | Two-wheel differential drive | Yes |
| (ii) "Operates at a distance from a human operator or supervisor based on commands or in response to sensor data or any combination thereof" | Drives itself from lidar data, or takes commands over Wi-Fi | Yes |
| (iii) "The combined weight of the device and, if applicable, ground station or docking station is over 4.4lbs" | About 5 kg (11 lb) | Yes, if the built robot really weighs ~5 kg; 4.4 lb is 2.0 kg |
| (iv)(i) "a sensor capable of perceiving its environment" | RPLIDAR A1M8 2D lidar | Yes |
| (iv)(ii) "a component that is capable of providing network connectivity (wired or wireless, including Bluetooth/WiFi, cellular, or satellite) with connection speeds of at least 200 kbps in either direction" | Raspberry Pi 5 has dual-band Wi-Fi, Bluetooth 5.0 and Gigabit Ethernet | Yes |
| (iv)(iii) "software running either locally or remotely ... that controls the robot's autonomous navigation or movement perception, data collection, or remote command-and-control" | Navigation stack on the Pi | Yes |
| Exclusions (B): connected vehicles, rail vehicles, UAS, underwater vehicles, FDA medical devices, fixed robots | None apply | Not excluded |

**Answer.** The demo robot as a whole plausibly is an "advanced robotic device". Assembled in
Canada (`final_assembly_country: CA`) it is "foreign-produced" at any domestic percentage, because
prong 1 fails. Moved to US final assembly, it is covered unless its domestic component share is
strictly above 65%. So the demo story holds: the robot is a covered device, and the BOM math
decides whether a US-assembled version escapes the list.

**Individual BOM lines are not "advanced robotic devices".** A motor, lidar, battery or SBC is
not itself a mobile device that meets all of (i)-(iv). The Raspberry Pi 5 radio is not a router
under the router entry. No BOM line comes from a producer named on the Covered List (Huawei, ZTE,
Hytera, Hikvision, Dahua, Kaspersky). The FCC 26-50 logic-bearing-hardware rule in docs/design
was not re-opened in this pass, so that check is still unverified.

## Uncertain, ask a human (counsel or the FCC)

1. Does a robot built from already-authorized modules (the Pi 5 radio has its own FCC grant)
   need its own equipment authorization, and so fall under the Covered List bar? The FAQ talks
   about "FCC equipment authorization" for the device but we did not find text on composite
   devices with modular radios. This decides whether the rule bites at all for a small builder.
2. Does a one-off hackathon prototype that is never marketed or imported need authorization?
   We assume the demo is illustrative of a product, not a product.
3. Weight: is the 4.4 lb test met by the finished robot only, or with the charging dock? Our
   robot is ~5 kg alone, so this only matters for a lighter variant.
4. Prong 1: is "manufactured in the United States" met by final assembly alone? It is undefined
   in the FAR (docs/design/01 flags this for counsel).
5. Firmware updates: docs/design/02 mentions a firmware-update waiver for covered devices; we
   did not open or verify that part of the FAQ in this pass.
