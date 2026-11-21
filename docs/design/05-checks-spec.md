# 05 Checks spec (fixes from 03-v2-review)

Owner: 3 (checks + data). Supply-chain math is in 04 section 7 (owner 2).
All functions are pure, take verified `Claim`s converted to SI by `units.py`, and return a
`CheckResult`. An unverified or missing input never fails a candidate; it makes the check Review.

```python
class CheckResult(BaseModel):
    candidate_id: str
    check: Literal["torque_cont", "torque_peak", "speed", "voltage", "fit_envelope",
                   "fit_ground", "fit_shaft"]
    verdict: Literal["pass", "fail", "review"]
    value: float | None; threshold: float | None; unit: str
    margin: float | None              # value / threshold
    claim_ids: list[str]               # the evidence behind `value`
    note: str                          # code-written, e.g. "holding torque only"
```

## 1. Units (fix 1: the LLM never converts)

| Raw unit (case-insensitive aliases) | SI | Factor |
|---|---|---|
| N-m, Nm, N.m | N·m | 1 |
| mN-m, mNm | N·m | 0.001 |
| oz-in, ozf-in, oz.in | N·m | 0.0070615518 |
| lb-in, lbf-in | N·m | 0.112984829 |
| lb-ft, lbf-ft | N·m | 1.35581795 |
| kgf-cm, kg-cm | N·m | 0.0980665 |
| rpm, RPM | rpm | 1 |
| mm / in | mm | 1 / 25.4 |
| V, VDC / A | V / A | 1 |
| USD / CAD | USD | 1 / dated Bank of Canada rate (sourced claim) |

Unknown unit -> claim stays unconverted -> any check needing it is Review.

## 2. Requirements (from v2 section 6, split into continuous and peak)

```
F_cont = m * g * (Crr*cos(theta) + sin(theta))
F_peak = F_cont + m * a
T_cont_req = r * F_cont / (n * G * eta) * SF
T_peak_req = r * F_peak / (n * G * eta) * SF
w_req_rpm  = v_max / (2*pi*r) * 60 * G
```
Demo robot (proposal): m 5 kg, r 0.06 m, n 2, G 1, eta 0.9, Crr 0.02, theta 5 deg, a 0.5,
SF 1.5 -> T_peak_req 0.388 N·m (computed), w_req 159 rpm at 1 m/s.

## 3. Rules by motor type (fix 2)

| Check | servo_integrated / bldc / brushed_dc | stepper |
|---|---|---|
| torque_cont | continuous_torque >= T_cont_req | torque_at_speed (at >= w_req) >= T_cont_req, else review "holding torque only" |
| torque_peak | peak_torque >= T_peak_req; if no peak claim, use continuous and review if continuous < T_peak_req | same source as above |
| speed | rated_speed (else max_speed, note it) >= w_req | review unless a torque_at_speed claim exists at >= w_req |
| voltage | servo_integrated: supply_voltage_min <= V_bus <= supply_voltage_max. bldc/brushed: rated_voltage within driver range from robot spec | rated_voltage is winding voltage: check rated_current <= driver max current; never compare to V_bus |

## 4. Fit (fixes 4)

NEMA table (`data/nema.yaml`, each row needs a vendor drawing URL before the demo):

| Frame | Flange sq (mm) | Bolt spacing (mm) | Pilot dia (mm) | Bolt hole | Common shafts (mm) |
|---|---|---|---|---|---|
| 17 | 42.3 | 31.0 | 22.0 | M3 thread | 5 |
| 23 | 57.2 | 47.14 | 38.1 | ~5.1 through | 6.35, 8 |
| 34 | 86.0 | 69.6 | 73.0 | ~5.5 through | 9.5, 12.7, 14 |

- fit_envelope: body_length + plate_t + clearance <= inboard_room_mm.
- fit_ground (new): r - flange/2 - clearance - plate_t - deck_t >= min_ground_clearance_mm.
  (Spike: NEMA 34 on 60 mm wheels leaves ~4 mm.)
- fit_shaft: shaft_diameter == wheel_bore_mm -> pass; differs -> review "needs hub adapter".

## 5. Verdict and fit badge

- Rejected: any check `fail` on verified data.
- Review: no fail, but any `review`.
- Pass*: every implemented check `pass`. UI text: "passes the checks we implemented".
- Fit badge: `drop_in` = Pass*, same frame and shaft as baseline, old bracket still fits.
  `close` = Pass* but bracket regenerated or adapter needed. `needs_review` = verdict Review.

## 6. Evidence rules (fix 5)

- Page claims: verified only if the normalized quote is found in a fresh TinyFetch html of
  `source_url`, and the number in the quote equals `raw_value` (string compare after
  whitespace/comma normalization).
- PDF claims: verified against `pdftotext` output of the downloaded PDF the same way.
- `extracted_by = gemini_vision` (tables as images, curves): never verified; can only produce
  Review.
- Origin: T1/T2 count as US for the compliance math; T3, rejected and none count as foreign.

## 7. Compliance number (fix 6)

The before/after domestic % shown on stage is whatever `domestic_share()` returns for the real
demo BOM with verified origins. If the swap does not cross 65%, the card says so and shows the
next cheapest line to move. The script adapts to the number, not the other way round.
