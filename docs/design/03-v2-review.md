# 03 Review of handoff v2 (Sat Nov 21, 2026, 3pm EST)

Verdict: GO. v2 is a stronger pitch than v1 and the riskiest piece (CAD regeneration) works.
Six things in the checks and the agent schema are wrong or will break on real motors; fix them
before anyone writes the check code. Schedule has already slipped one milestone.

## What was tested

- CadQuery 2.8.0 installs from pip on Python 3.12 (local spike, not committed; superseded by `cad/cad_worker/` on main). A parametric robot
  (base, e-box, 2 wheels, 2 motors, 2 brackets, caster) regenerates for NEMA 17/23/34 and exports
  GLB + STEP in about 0.25 s per variant. GLB keeps part names (`bracket_L`, `motor_R`, ...), so
  the viewer can highlight the bracket by name. Spike placement has bugs (one motor sits on the
  wrong side); the toolchain is fine. Pin Python 3.12 in the Docker image (3.13 untested).
- Legal claim in v2 section 3 checked against 48 CFR 25.003 (eCFR, current to Nov 19, 2026):
  a domestic end product needs "components mined, produced, or manufactured in the United States"
  above 65%. A US-made motor counts whole, whatever its magnets. Confirmed.
  - Correction: the iron/steel exception is about END PRODUCTS that are >50% iron/steel by cost,
    not about components. A robot is not, so drop "(except iron and steel)".
  - New, flag for counsel, do not build: the same text says foreign components "of the same
    class or kind" the government has found not available domestically (FAR 25.104 list) are
    treated as domestic. Whether the FCC applies that is unknown.
- Real US-made NEMA targets found (evidence tier in brackets):
  - Teknic ClearPath-SD (integrated servo, NEMA 23/34, from $265; NEMA 17 "available later this
    year"). Site: "we'll build and ship it to you from our New York manufacturing plant". [T2]
  - Moog Animatics SmartMotor SM23165D and others: news page says "produced in our Murphy, NC
    facility" and names SKUs. [T1-ish: model-specific statement]
  - Pittman (AMETEK), NEMA 23 brushless: only an HQ address in Harleysville, PA. [T3, not
    evidence] A good live example of the verifier refusing a weak claim.
  - Every credible US-made candidate found is a servo/BLDC, not a stepper. That matters below.

## Must-fix before building checks

1. The schema makes the LLM do arithmetic. `rated_torque_nm`, `body_length_mm`, `price_usd`
   force the agent to convert oz-in, lb-in, inches, CAD. That breaks the "LLM never does math"
   rule and breaks the verbatim verifier (the page says "425 oz-in", not "3.0"). Fix: capture
   value + unit exactly as written (`torque: {value: 425, unit: "oz-in", quote: "..."}`); code
   converts with a units table.
2. Steppers break torque, speed and voltage checks.
   - Stepper "torque" on a page is holding torque; usable torque falls with speed.
   - Steppers have no rated speed.
   - Stepper "rated voltage" is winding voltage (2-4 V), so every stepper fails V_bus.
   Fix: add `motor_type` (servo | bldc | stepper | brushed). Servo/BLDC: continuous torque,
   rated speed, supply voltage range. Stepper: torque at operating speed from the pull-out curve
   if the datasheet has one, else Review with a stated derate. Pick a demo baseline and
   candidates that are servos/BLDC; that is also what the US makers sell.
3. Gear ratio is unstated. Computed with the v2 formula (r = 60 mm, 2 motors, G = 1, eta 0.9,
   Crr 0.02, a = 0.5 m/s^2, SF 1.5): 5 kg flat = 0.174 Nm per motor; 5 kg on 5 deg = 0.388 Nm;
   15 kg on 10 deg = 1.80 Nm. Wheel speed at 1 m/s = 159 rpm. A light (~5 kg) indoor robot
   works direct-drive with NEMA 23 servos; a heavier one needs a gearbox, which is another part
   with its own origin and flange. Recommendation: ~5 kg, direct drive, G = 1 fixed.
4. Fit check misses the constraint that actually bites: motor axis sits at wheel-axle height,
   so the flange hangs below it. Ground clearance = r - frame/2 - clearance - plate. In the spike
   NEMA 34 on 60 mm wheels leaves about 4 mm. Add it. Also add bolt hole size to the NEMA table
   (NEMA 17 M3; NEMA 23 ~5.1 mm through; NEMA 34 ~5.5 mm through, verify per vendor drawing).
5. Datasheet numbers cannot be string-matched against page HTML. Verify PDF-derived values
   against the PDF text layer (pdftotext). Values Gemini read from an image or a curve are
   "unverified": they can make a candidate Review, never Pass*.
6. "38% -> 67%" must come out of a real BOM, not the script. Replacing two drive motors moves
   ~29 points only if they are a large share of component cost. Build the BOM first and let
   the calculator pick the line; remember duty and freight count in foreign parts' cost.

## Schedule and scope

- Now ~3pm EST Sat. The "Sat 2pm: bracket regenerates" milestone has passed unless a teammate
  hit it; the spike covers most of it. ~13 h to the 4am freeze.
- v2 touches 9 sponsor technologies (TinyFish x5 products, Gemini, Vultr, Tiger Data, Auth0,
  Entire, GoDaddy). Suggested tiers:
  - Must: TinySearch/TinyFetch + TinyAgent with live tiles, Fetch-HTML verifier, Gemini
    datasheet extraction, CAD + checks.
  - Should: Vultr deploy, Tiger Data agent_runs + success-by-site panel (doubles as TinyFish
    evidence), STEP export.
  - Could: TinyBrowser RFQ form, TinyMonitor, tournament of 3, Auth0, GoDaddy, Entire extras.
- Ask organizers whether a team can win more than one MLH prize (unverified).

## Pitch risk to prepare for

"What if the motor is not NEMA?" Answer: the engine regenerates parts defined by a mechanical
interface standard (NEMA flanges today; ISO 9409 tool flanges, DIN rail, standard bearing
sizes next). Say "parametric template" on stage, as v2 already plans.
