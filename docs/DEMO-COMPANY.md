# Demo company for onboarding: Northfield Robotics and the AR4 arm

A demo case for trying the onboarding flow by hand. The robot is real: the AR4, a six-axis
articulated robotic arm designed by Annin Robotics for robotics education, research, automation
and experimentation. The parts list is read from Annin Robotics' 37-page AR4 bill of materials
PDF. The company is made up: Northfield Robotics, its customers, budget and deadline are
invented so the risk engine has stated priorities to work with.

Paste each answer into the matching onboarding step, exactly as written. The reading of these
answers is recorded, so the whole case replays offline with no token and no credit. If you
change an answer or a part name in the CSV, the recording no longer matches: the site then asks
for the live token and makes real Gemini calls.

## What the parts list is, and is not

[demo-company-bom.csv](demo-company-bom.csv) has 60 lines taken from the PDF. Each line keeps
the component name, quantity and part number as the PDF prints them, and the PDF page it comes
from.

- **Real, from the PDF:** component names, quantities, part numbers, source pages, the
  Stepperonline supplier on the motors, drivers and J4 bracket, and the bracket's $1.96 price.
- **Real, from our research:** the J2 motor's price ($152.52), origin (CN) and stock
  (`data/projects/ar4_club.json`, with its sources).
- **Illustrative, made up for the demo:** every other price, country of origin, supplier, stock
  status, lead time and customs code. The PDF states none of these. They are plausible values
  chosen so the risk engine has something to score, and each line's `notes` says so. Do not
  quote them as facts about the AR4 or its suppliers.
- The parts list is not evidence that any part meets a rule or regulation.
- Lines are grouped into six subsystems in the `category` column:

| Subsystem | Lines | What is in it |
|---|---|---|
| actuation | 6 | the six joint motors, J1 to J6 |
| transmission | 22 | bearings, thrust washers, belts, pulleys, shafts |
| structure | 13 | machined aluminum parts per joint, fasteners, 3D printed parts, cable sleeve and glands |
| electronics | 10 | Teensy 4.1, breakout board, cables, connectors, fan |
| power | 6 | stepper drivers, power jack, switch, power distribution block |
| sensors | 3 | Hall effect sensors, limit switches, magnets |

To stay near 60 lines, three groups are one line each: the machined aluminum parts of one joint
(the line names every part), the 39 fastener sizes (311 pieces) and the 29 3D printed parts.

## Step 1: Who are you, and what are you building?

> We are Northfield Robotics, a 12-person startup in Waterloo, Ontario. We build the AR4 Cell: an Annin Robotics AR4 six-axis robotic arm that we assemble and sell ready to run for robotics education, research and light automation.

## Step 2: Who buys it, where is it assembled and where will it run?

> We sell to universities and research labs in Canada and the US, including US federal research labs. Final assembly is in Canada. The arms run in the US and Canada. Downtime is costly: a lab course or an experiment stops when the arm does.

## Step 3: What limits matter: budget, deadline, anything to avoid?

> We have about $2,500 of parts per arm and need parts within 30 days. We want to avoid motors that depend on Chinese rare-earth magnets, and any supplier on a US restricted list.

## Step 4: Files

Upload [demo-company-bom.csv](demo-company-bom.csv) as the parts list. There is no CAD file for
this company; skip that upload.

## Step 5: the drivetrain question is skipped

The site recognises this parts list as the AR4 by the J2 motor's part number, so it goes from
the files step straight to the review screen. A wheeled parts list still gets the drivetrain
question.

## What to expect on the review screen

| Fact | Value |
|---|---|
| Name | Northfield Robotics |
| Kind | company |
| Robot | AR4 Cell |
| Use | robotics education, research and light automation |
| Sells to US federal buyers | yes |
| Deployed in | US, CA |
| Final assembly | CA |
| Uptime critical | yes |
| Wants to avoid | motors that depend on Chinese rare-earth magnets, and any supplier on a US restricted list |
| Parts budget per robot | $2,500 |
| Needs parts in | 30 days |

Above the facts, the review screen shows the J2 joint numbers a replacement motor is checked
against (payload 1.9 kg, reach 629 mm, gear ratio 50 : 1, bus voltage 24 V, safety factor 1.5),
marked "from our research". No wheel numbers are shown.

## How the J2 motor is handled

The J2 shoulder motor (`23HS22-2804D-YGS50-AR4`) is the part the agents search a replacement
for. The parts list carries the same part number as the motor already researched for the AR4
club project (`data/projects/ar4_club.json`), so the job reuses that research:

- The joint requirement comes from the AR4 arm numbers in that file (1.9 kg payload, 629 mm
  reach, 50:1 gearbox, 24 V), each with its source or marked as an assumption. The existing
  arm checks run on it unchanged.
- The before and after 3D models are the AR4 with the J2 motor mount, as in the AR4 club case.
- Price ($152.52), origin (CN, company-level) and customs code of the J2 line come from that
  research, not from the PDF. The line's note says so. All other lines keep `unknown`.

## What to expect in the results

Checked in replay with the recordings in this repo and the answers above:

- A risk row and a recommendation for all 60 parts: 42 to investigate, 18 to keep. Parts total
  about $1,461 per arm, inside the $2,500 budget.
- **J5 linear drive motor first (priority 8 of 9):** its 45 day lead time is past the 30 day
  need-by, so the line is blocked.
- **The other five motors next (priority 7):** made in China for a company that sells to US
  federal buyers, with 41.5% added US duty, and likely dependent on rare-earth magnets
  (inferred, shown as inferred). The J2 motor names Teknic CPM-SDSK-2331S-RLN (US) as the best
  candidate so far.
- **The 4 mm magnets (priority 6):** the parts list marks them `ndfeb_magnets`, which is what
  the company said it wants to avoid, so this is a stated conflict, not an inferred one.
- **Other parts made outside the US** are a concern for the federal buyer; **US-made parts**
  (machined aluminum, the Teensy, inch-size thrust bearings, belts) are kept.
- Three alternatives for the J2 motor from the recorded TinyFish runs: two for review, one
  rejected.

Only the J2 motor gets alternatives, so no line reaches "re-source" or "dual-source" in this
case: those actions need a checked alternative.

For live TinyFish research on the J2 motor, open the site with `?live=1` and press "Run live".
That spends TinyFish and Gemini credit and needs the live token.
