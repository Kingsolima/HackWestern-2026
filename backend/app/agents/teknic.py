"""Known-good demo target: Teknic ClearPath-SD (HANDOFF-v3 §10).

The family page has no per-model specs; they sit on model pages behind the model list, and
the manufacturing claim is on another page. That makes it a real multi-page TinyAgent job.
"""

TEKNIC_URL = "https://teknic.com/products/clearpath-brushless-dc-servo-motors/clearpath-sd/"


def build_goal() -> str:
    return """\
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
   - quote = the exact text copied from the page that contains that number (a short \
label + value), character for character.
   - source_url = the URL of the page where you read it.
   - at_speed_value / at_speed_unit only if the page ties the torque to a speed, else null.
4. Find where Teknic states ClearPath motors are manufactured (try the model page, then the \
About page). Put the exact sentence in origin_quote, its page URL in origin_source_url, and \
the country it names in country_of_origin. "Designed in" or a headquarters address is NOT \
a manufacturing statement: leave origin fields null in that case.
5. manufacturer = "Teknic", part_number = the model's part number, motor_type = \
"servo_integrated", nema_frame = "23", product_url = the model page URL, datasheet_url = a \
manual/datasheet PDF link if one is on the model page, else null.

Rules: never guess or fill placeholders; use null (or omit a spec) when not shown. \
If a CAPTCHA, bot check or access-denied page blocks you, return status "blocked" with the \
reason. If you cannot find any NEMA 23 SDSK model, return status "not_found". If some fields \
are missing, return status "incomplete" and list what is missing in reason. Otherwise status \
"success".
"""
