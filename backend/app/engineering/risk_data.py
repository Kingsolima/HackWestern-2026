"""Sourced evidence for the risk factors, read from data files written by research (every value
there carries a URL and a quote): the article's bottleneck levels, US duty stacks, and the
restricted-entity lists. Canadian duty has not been researched: it reads as unknown."""

import re
from functools import cache
from pathlib import Path

import yaml

from app.config import Settings
from app.engineering.risk import RiskInputs
from app.schemas import BomLine, Criteria, Level

ARTICLE_PDF = "docs/turning-humanoid-supply-chain-constraints-into-billion-dollar-wins.pdf"
LIST_FILES = {
    "uflpa": "uflpa_entity_list.yaml",
    "dod_1260h": "dod_1260h.yaml",
    "fcc_covered": "fcc_covered_list.yaml",
}


def _data() -> Path:
    return Settings().data_dir


@cache
def _yaml(rel: str) -> dict:
    return yaml.safe_load((_data() / rel).read_text())


def bottleneck(component_class: str | None) -> tuple[Level, str | None, str]:
    """(level, source, quote) from the article; unknown for classes it does not place."""
    entry = _yaml("research/article_map.yaml")["classes"].get(component_class or "")
    if entry is None:
        return "unknown", None, ""
    return entry["level"], f"{ARTICLE_PDF}#page={entry['page']}", entry["quote"]


def duty_pct(hts: str | None, origin: str | None, criteria: Criteria) -> tuple[float | None, str]:
    """Largest added import duty over the criteria's duty countries, in percent, with a note.
    Goods made in the importing country pay none. Unknown when any market lacks data."""
    if not criteria.duty_countries:
        return None, "no import market in the criteria"
    if origin is None:
        return None, "origin unknown, so duty cannot be set"
    worst = 0.0
    notes = []
    for market in criteria.duty_countries:
        if origin == market:
            notes.append(f"made in {market}: no import duty")
            continue
        if market != "US":
            return None, f"{market} duty not researched"
        pct, note = _us_duty(hts, origin)
        if pct is None:
            return None, note
        worst = max(worst, pct)
        notes.append(note)
    return worst, "; ".join(notes)


def _us_duty(hts: str | None, origin: str) -> tuple[float | None, str]:
    codes = _yaml("research/tariffs.yaml")["hts_codes"]
    entry = codes.get(hts or "")
    layers = (entry or {}).get("by_origin", {}).get(origin)
    if not isinstance(layers, list):
        return None, f"US duty for HTS {hts} from {origin} not researched"
    total = 0.0
    for layer in layers:
        m = re.search(r"(\d+(?:\.\d+)?)%", layer)
        if m is None:
            return None, f"US duty layer '{layer}' has no plain rate"
        total += float(m.group(1))
    return total, f"US: {', '.join(layers)} (HTS {hts})"


@cache
def _list_names(key: str) -> tuple[str, ...]:
    data = _yaml(f"lists/{LIST_FILES[key]}")
    rows = data.get("entities") or data.get("named_entities") or []
    names = (r.get("name") or r.get("producer") if isinstance(r, dict) else str(r) for r in rows)
    return tuple(n for n in (_norm(name or "") for name in names) if n)


def _norm(name: str) -> str:
    name = re.sub(r"\([^)]*\)", " ", name.lower())
    name = re.sub(r"\b(co|ltd|inc|corp|corporation|company|limited|group|llc)\b\.?", " ", name)
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", name).split())


def list_hits(manufacturer: str | None, criteria: Criteria) -> list[str]:
    """Blocking lists that name this manufacturer: normalized names, one contains the other as
    whole words. A screen, not a legal determination: a hit blocks the line for review."""
    if not manufacturer:
        return []
    m = _norm(manufacturer)
    if len(m) < 3:
        return []
    hits = []
    for key in criteria.blocking_lists:
        if any(
            len(n) >= 3 and (f" {m} " in f" {n} " or f" {n} " in f" {m} ") for n in _list_names(key)
        ):
            hits.append(key)
    return hits


def inputs_for(
    line: BomLine, criteria: Criteria, eligible_alternatives: int | None = None
) -> RiskInputs:
    level, source, _quote = bottleneck(line.component_class)
    pct, note = duty_pct(line.hts_code, line.origin_country, criteria)
    return RiskInputs(
        eligible_alternatives=eligible_alternatives,
        bottleneck=level,
        bottleneck_source=source,
        duty_pct=pct,
        duty_note=note,
        list_hits=list_hits(line.manufacturer, criteria),
    )
