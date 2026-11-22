"""Swap targets: where the swap worker sends TinyAgent, and what it asks for.

The output schema ships inside the package (the Docker image has no docs/); a test keeps it
identical to the contract in docs/design/schemas/motor_candidate.tinyfish.json.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MOTOR_SCHEMA: dict[str, Any] = json.loads(
    (Path(__file__).parent / "motor_candidate.tinyfish.json").read_text()
)


@dataclass(frozen=True)
class SwapTarget:
    name: str
    url: str
    goal: str
    max_duration_s: int = 240


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
2. Pick ONE NEMA 23 SDSK model (part number starts with CPM-SDSK-23) and open its \
specification / model information page.
3. From that model's page, fill `specs` with every one of these that is shown: \
continuous_torque, peak_torque, max_speed, supply_voltage_min, supply_voltage_max, \
body_length, shaft_diameter, price. For each spec:
   - value = the number exactly as shown, unit = the unit exactly as shown (e.g. "oz-in", \
"N-m", "RPM", "VDC", "in", "mm", "USD"); do not convert units.
   - quote = the row label and the value exactly as they appear on the page, character for \
character. Do not add colons, words or labels that are not on the page. When the label and the \
value sit in separate table cells, join them with one space (e.g. "Length 3.34 in (84.84 mm)"). \
For price, quote the price text exactly as displayed (e.g. "$293").
   - source_url = the URL of the page where you read it.
   - at_speed_value / at_speed_unit only if the page ties the torque to a speed, else null.
4. Find where this model's country of origin or manufacturing location is stated. First look \
for a "Country of Origin" row in the model page's spec table and quote that row (label + value, \
as above); only if there is none, look for a manufacturing statement on the About page. Put the \
exact text in origin_quote, its page URL in origin_source_url, and the country it names in \
country_of_origin. "Designed in" or a headquarters address is NOT \
a manufacturing statement: leave origin fields null in that case.
5. manufacturer = "Teknic", part_number = the model's part number, motor_type = \
"servo_integrated", nema_frame = "23", product_url = the model page URL, datasheet_url = a \
manual/datasheet PDF link if one is on the model page, else null.

Rules: never guess or fill placeholders; use null (or omit a spec) when not shown. \
If a CAPTCHA, bot check or access-denied page blocks you, return status "blocked" with the \
reason. If you cannot find any NEMA 23 SDSK model, return status "not_found". If some fields \
are missing, return status "incomplete" and list what is missing in reason. Otherwise status \
"success".
""",
)

SWAP_TARGETS: tuple[SwapTarget, ...] = (TEKNIC,)
