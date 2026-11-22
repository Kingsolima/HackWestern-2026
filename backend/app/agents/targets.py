"""Swap targets: where the swap worker sends TinyAgent, and what it asks for.

The output schema ships inside the package (the Docker image has no docs/); a test keeps it
identical to the contract in docs/design/schemas/motor_candidate.tinyfish.json.
"""

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MOTOR_SCHEMA: dict[str, Any] = json.loads(
    (Path(__file__).parent / "motor_candidate.tinyfish.json").read_text()
)


@dataclass(frozen=True)
class SwapTarget:
    """`goal` is a str.format template over bus_v, cont_oz_in and peak_oz_in, filled from the
    robot requirement so the agent searches for a motor that can pass; the checks decide."""

    name: str
    url: str
    goal: str
    max_duration_s: int = 300

    def goal_for(self, t_cont_nm: float, t_peak_nm: float, bus_v: float, frame: str = "23") -> str:
        oz_in = 0.0070615518
        return self.goal.format(
            frame=frame,
            bus_v=f"{bus_v:g}",
            cont_oz_in=math.ceil(t_cont_nm / oz_in),
            peak_oz_in=math.ceil(t_peak_nm / oz_in),
        )


# Started from Omar's goal for the first live Teknic run (commit 3e8f9a3). The family page has
# no per-model specs; they sit on model pages. Quote rules tightened after the first live job:
# the agent added labels and colons that are not on the page, so the verifier rejected them.
TEKNIC = SwapTarget(
    name="teknic-clearpath-sd",
    url="https://teknic.com/products/clearpath-brushless-dc-servo-motors/clearpath-sd/",
    goal="""\
You are a sourcing engineer collecting verifiable specs for ONE motor. Do not buy, log in, \
fill forms or sign up for anything.

1. On this Teknic ClearPath-SD page, go to the list of ClearPath-SD models \
("All ClearPath models", filtered to SDSK if possible).
2. Pick ONE NEMA {frame} SDSK model (part number starts with CPM-SDSK-{frame}) for a robot with a \
{bus_v} VDC bus that needs, at {bus_v} VDC, a Cont. (RMS) Torque of at least {cont_oz_in} oz-in \
and a Peak Torque of at least {peak_oz_in} oz-in. Compare the models (list filters or model \
pages) and pick the cheapest one that meets both; if none does, pick the one with the highest \
Cont. (RMS) Torque. Open its model information page and select the {bus_v} VDC input voltage.
3. From that model's page, fill `specs` with every one of these that is shown: \
continuous_torque, peak_torque, max_speed, supply_voltage_min, supply_voltage_max, \
body_length, shaft_diameter, price. For each spec:
   - value = the number exactly as shown, unit = the unit exactly as shown (e.g. "oz-in", \
"N-m", "RPM", "VDC", "in", "mm", "USD"); do not convert units.
   - quote = the row label and the value exactly as they appear on the page, character for \
character. Do not add colons, words or labels that are not on the page. When the label and the \
value sit in separate table cells, join them with one space (e.g. "Length 3.34 in (84.84 mm)"). \
For price, quote the price text exactly as displayed (e.g. "$293").
   - Read torque and speed in the {bus_v} VDC column. For supply_voltage_min and \
supply_voltage_max, quote the "Input (Bus) Voltage Range" row.
   - source_url = the URL of the page where you read it.
   - at_speed_value / at_speed_unit only if the page ties the torque to a speed, else null.
4. Find where this model's country of origin or manufacturing location is stated. First look \
for a "Country of Origin" row in the model page's spec table and quote that row (label + value, \
as above); only if there is none, look for a manufacturing statement on the About page. Put the \
exact text in origin_quote, its page URL in origin_source_url, and the country it names in \
country_of_origin. "Designed in" or a headquarters address is NOT \
a manufacturing statement: leave origin fields null in that case.
5. manufacturer = "Teknic", part_number = the model's part number, motor_type = \
"servo_integrated", nema_frame = "{frame}", product_url = the model page URL, datasheet_url = a \
manual/datasheet PDF link if one is on the model page, else null.

Rules: never guess or fill placeholders; use null (or omit a spec) when not shown. \
If a CAPTCHA, bot check or access-denied page blocks you, return status "blocked" with the \
reason. If you cannot find any NEMA {frame} SDSK model, return status "not_found". If some fields \
are missing, return status "incomplete" and list what is missing in reason. Otherwise status \
"success".
""",
)

SWAP_TARGETS: tuple[SwapTarget, ...] = (TEKNIC,)


# For pages found by discovery that need clicking. Same output contract as the Teknic goal.
GENERIC_GOAL = """\
You are a sourcing engineer collecting verifiable specs for ONE motor. Do not buy, log in, \
fill forms or sign up for anything.

1. Starting from this page, find ONE NEMA {frame} servo, integrated servo, closed-loop stepper \
or brushless DC motor model sold by this manufacturer, for a robot with a {bus_v} VDC bus that \
needs at least \
{cont_oz_in} oz-in continuous torque and {peak_oz_in} oz-in peak torque. Prefer the cheapest \
model that meets both; if none clearly does, pick the one with the highest continuous torque. \
Open that model's own specification page or datasheet.
2. Fill `specs` with every one of these that is shown: continuous_torque, peak_torque, \
rated_speed, max_speed, supply_voltage_min, supply_voltage_max, rated_voltage, rated_current, \
body_length, shaft_diameter, price. For each spec:
   - value = the number exactly as shown, unit = the unit exactly as shown; do not convert.
   - quote = the label and the value exactly as they appear on the page, character for \
character. Do not add colons, words or labels that are not on the page. When the label and the \
value sit in separate table cells, join them with one space.
   - source_url = the URL of the page where you read it.
   - at_speed_value / at_speed_unit only if the page ties the torque to a speed, else null.
3. Find where this model's country of origin or manufacturing location is stated: a "Country \
of Origin" row first, otherwise a manufacturing statement on the company's site. Put the exact \
text in origin_quote, its page URL in origin_source_url and the country in country_of_origin. \
"Designed in" or a headquarters address is NOT a manufacturing statement: leave the origin \
fields null in that case.
4. manufacturer, part_number, motor_type, nema_frame, product_url (the model page) and \
datasheet_url (a PDF link if shown, else null).

Rules: never guess or fill placeholders; use null (or omit a spec) when not shown. If a \
CAPTCHA, bot check or access-denied page blocks you, return status "blocked". If the site sells \
no such motor, return status "not_found". If some fields are missing, return status \
"incomplete" and list what is missing in reason. Otherwise status "success".
"""
