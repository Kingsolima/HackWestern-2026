# Demo company for onboarding: Northfield Robotics

A made-up company for trying the onboarding flow by hand. Nothing here is real: the company,
the robot, the prices and the countries are invented. Paste each answer into the matching
onboarding step.

Its numbers differ from the recorded example (`data/onboarding_example.json`), so the job needs
real agent runs: the site asks for the live token and the run spends TinyFish and Gemini credit.
To stay in free replay, use "Use the example" in onboarding instead.

## Step 1: Who are you, and what are you building?

> We are Northfield Robotics, a 12-person startup in Waterloo, Ontario. We build Porter, a
> wheeled robot that moves supply carts between wards and the pharmacy in hospitals.

## Step 2: Who buys it, where is it assembled and where will it run?

> We sell to US Veterans Affairs hospitals, which are federal buyers, and to private hospital
> networks in the US and Canada. Final assembly is in Canada. The robots run in the US and
> Canada. Downtime is costly: when a robot stops, nurses go back to pushing carts by hand.

## Step 3: What limits matter: budget, deadline, anything to avoid?

> We have about $1,100 of parts per robot and need parts within 45 days. We want to avoid
> motors that depend on Chinese rare-earth magnets, and any supplier on a US restricted list.

## Step 4: Files

Upload [demo-company-bom.csv](demo-company-bom.csv) as the parts list (13 lines, $896 per
robot). There is no CAD file for this company; skip that upload.

| Part | Category | Qty | Unit cost (USD) | Origin |
|---|---|---|---|---|
| Drive motor (NEMA 23 stepper) | motor | 2 | 62.00 | CN |
| Planetary gearbox 5:1 | gearbox | 2 | 48.00 | CN |
| Motor driver | electronics | 2 | 35.00 | CN |
| Welded aluminum chassis | frame | 1 | 140.00 | US |
| Drive wheel 150 mm | frame | 2 | 18.00 | CN |
| Caster wheel | frame | 2 | 9.00 | TW |
| 24V battery pack | battery | 1 | 110.00 | KR |
| Single-board computer | compute | 1 | 80.00 | GB |
| 2D lidar | lidar | 1 | 99.00 | CN |
| Wheel encoder | encoder | 2 | 28.00 | US |
| Electronics enclosure | frame | 1 | 30.00 | CA |
| Wiring harness | electronics | 1 | 25.00 | US |
| Fasteners | frame | 1 | 12.00 | US |

## Step 5: What else should we know about the drivetrain?

> It has 2 drive motors, each through a 5:1 gearbox, on wheels with a 75 mm radius. There is
> 110 mm of space for each motor and its bracket. It weighs 18 kg with payload, drives at up
> to 1.2 m/s, climbs a 6 degree ramp and accelerates at 0.6 m/s². The bus voltage is 24 V.

## What to expect on the review screen

| Fact | Value |
|---|---|
| Name | Northfield Robotics |
| Kind | company |
| Robot | Porter |
| Sells to US federal buyers | yes |
| Deployed in | US, CA |
| Final assembly | CA |
| Uptime critical | yes |
| Parts budget per robot | $1,100 |
| Needs parts in | 45 days |

With these numbers each drive motor needs about 0.28 N·m continuous and 0.41 N·m peak at about
760 RPM, which a NEMA 23 servo can meet. The job searches for a replacement for the NEMA 23
drive motor and maps supply risk for all 13 parts.
