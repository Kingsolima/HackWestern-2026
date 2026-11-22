# Build plan v4: supply-risk redesign engine (design checkpoint)

Status: APPROVED 2026-11-21 ("go with your assumptions"), with decision 1 changed: Stretch also
gets the deep loop and CAD, on an illustrative actuator. Builds on BUILD-PLAN-v3.md and HANDOFF-v3.md; everything
there that is not changed here stays (live agents, the verifier, code-only numbers and verdicts,
record/replay, SSE contract, the regenerated part in CAD).

## 1. Problem, restated

A robotics team tells us who it is, what its robot does, and what is in it. The engine:

1. Works out what matters for that team (intake): performance needs from the robot, and which
   supply risks it cannot tolerate from its use case and situation.
2. Splits the BOM into core domains (actuation, sensing, compute, power, structure) and maps,
   per component, who can supply it, from which country, and how available it really is.
3. Goes deep on one component (the actuator): live agents find alternatives on real sites, code
   verifies every quote, checks them against the requirement, and CAD regenerates the mount.
4. Ends with the team's decision: which components to keep, re-source or dual-source, with
   whom, ranked by risk reduction against cost.

"Domestic content" is one possible requirement, switched on by a rule (for example, sells to
US federal buyers). It is no longer the goal. Source of the framing and the starting risk map:
docs/turning-humanoid-supply-chain-constraints-into-billion-dollar-wins.pdf.

Unchanged rule: no LLM produces a number, a verdict, a risk level or an origin tier. An LLM may
extract a fact with a quote; the verifier confirms the quote; code applies the rules.

## 2. Demo cases

| | Boston Dynamics Stretch | Western robotics club, AR4 arm |
|---|---|---|
| Kind | company | club project (London, Ontario) |
| Facts | verified live from bostondynamics.com (use case, markets, uptime statements) | stated by the club, labelled "stated" |
| BOM | ILLUSTRATIVE (real parts of the right class, labelled as not BD's) | real, public (Annin AR4 MK5 + StepperOnline motors) |
| What drives requirements | uptime-critical logistics, deploys in the US | budget, need-by date, imports into Canada |
| Deep component | ILLUSTRATIVE arm shoulder actuator (motor + gearbox, sized from the public 50 lb case weight) | J2 shoulder actuator (NEMA 23 + 50:1 gearbox) |
| CAD | ILLUSTRATIVE Stretch-like model (mobile base + arm), mount regenerated, labelled | J2 motor mount regenerated in the AR4 arm |

Pitch: same engine, two users, opposite priorities.

## 3. Pipeline

```
 project file (data/projects/<id>.json)
        |
 INTAKE ---------- company: TinyFetch official pages -> Flash extracts facts with quotes
        |          -> verify_claim; club: facts marked "stated"
 CRITERIA -------- code rules: facts -> objectives, thresholds, blocking lists (with reasons)
        |
 REQUIREMENT ----- code formula per robot kind: wheeled (05 section 2) or arm joint (new)
        |
 RISK_BASELINE --- per BOM line: factors -> level; replaces COMPLIANCE_BASELINE's card
        |          (the old card is still emitted; domestic % only when a rule asks for it)
 PLAN/DISCOVER/TRIAGE/EXTRACT/VERIFY/CHECK   (unchanged, on the deep line)
        |
 ALTERNATIVES ---- deep line: verified live candidates; other lines: sourced research rows
        |
 RANK ------------ objectives come from CRITERIA, not a fixed list
 RECOMMEND ------- per line keep / dual_source / re_source, ranked
 BUILD ----------- baseline + regenerated mount (Omar's worker)
```

## 4. Data shapes (all additive)

```python
Domain = Literal["actuation", "sensing", "compute", "power", "structure", "other"]
Level = Literal["low", "medium", "high", "unknown"]
FactBasis = Literal["verified", "stated"]

class ProjectFacts(BaseModel):            # each field None when unknown
    sells_to_us_federal: bool | None
    deploy_countries: list[str]           # ISO-2
    uptime_critical: bool | None
    budget_usd: float | None
    need_by_days: int | None

class Fact(BaseModel):                    # one per ProjectFacts field that is set
    field: str; value: str; basis: FactBasis; claim_id: str | None

class Project(BaseModel):
    id: str; kind: Literal["company", "club"]; name: str; robot: str; use_case: str
    robot_kind: Literal["wheeled", "arm"]; robot_params: dict   # formula inputs
    deep_line: str                        # BOM line id the agents work on
    bom: list[BomLine]; facts: ProjectFacts; fact_basis: list[Fact]

class BomLine(BaseModel):                 # extends today's BomRow fields
    id: str; domain: Domain; qty: int; part: str; manufacturer: str | None
    unit_price_usd: float | None; origin_country: str | None; origin_tier: OriginTier | None
    availability: Literal["in_stock", "lead_time", "out_of_stock", "unknown"]
    lead_time_days: int | None; illustrative: bool = False; sources: list[Source]

class Criteria(BaseModel):
    objectives: list[Objective]           # adds "supply_risk", "lead_time"; domestic reuses us_first
    domestic_threshold: float | None      # 0.65 only when a rule switches it on
    max_lead_time_days: int | None
    blocking_lists: list[str]             # "fcc_covered", "dod_1260h", "uflpa"
    reasons: list[CriterionReason]        # rule id, fact field, text

class RiskFactor(BaseModel):
    name: Literal["sources", "bottleneck", "trade", "restricted", "availability"]
    level: Level; value: str; reason: str; source_urls: list[str]

class LineRisk(BaseModel):
    line_id: str; factors: list[RiskFactor]; overall: Level

class Alternative(BaseModel):
    id: str; line_id: str; manufacturer: str; part_number: str
    origin_country: str | None; origin_tier: OriginTier | None
    unit_price_usd: float | None; availability: ...; lead_time_days: int | None
    verdict: Verdict | None               # spec checks; None for non-deep lines
    risk: LineRisk; live: bool            # live agent find vs research row

class Recommendation(BaseModel):
    line_id: str; action: Literal["keep", "dual_source", "re_source"]
    alternative_id: str | None; cost_delta_usd: float | None
    risk_before: Level; risk_after: Level; reason: str
```

New SSE events (one payload model each, additive): `project` (facts + criteria),
`risk_line` (LineRisk + the BomLine), `alternative`, `recommendation`.

## 5. Rules (code, each with a test)

Criteria rules:

| id | when | effect |
|---|---|---|
| C1 | sells_to_us_federal | objective domestic, threshold 0.65; blocking dod_1260h, fcc_covered |
| C2 | deploy_countries has US | trade factor uses US duty stack; blocking uflpa |
| C3 | deploy_countries has CA | trade factor uses Canadian duty |
| C4 | uptime_critical | objective supply_risk |
| C5 | need_by_days set | objective lead_time; max_lead_time_days = need_by_days |
| C6 | budget_usd set | objective cost; BOM total over budget is a finding |
| always | | objective performance (spec checks are a hard gate) |

Risk factor levels per line (overall = worst known factor; unknown factors are shown, never
counted as low):

| factor | low | medium | high |
|---|---|---|---|
| sources | 2+ alternatives that pass | 1 | 0 |
| bottleneck | article tier low | medium | high (article's own tier for the domain) |
| trade | 0% added duty into the deploy country | > 0% | >= 25% |
| restricted | no list hit | | any hit on a blocking list (also blocks the line) |
| availability | in stock / lead time within need-by | lead time unknown vs need-by | out of stock or over need-by |

Recommendation per line (the proposed Tygo core, section 8):
- current line blocked (restricted, or out of stock / over need-by) -> re_source to the
  cheapest alternative that passes and is not blocked;
- an alternative with lower overall risk at equal or lower cost -> re_source to it;
- an alternative with lower overall risk at higher cost -> dual_source with it;
- otherwise keep.
Lines are ranked by risk reduction (levels dropped) descending, then cost delta ascending.

## 6. Arm joint requirement (new formula, same Requirement type)

For J2 at full horizontal extension (worst static case), with payload m_p at reach L and each
link i of mass m_i with centre of mass at r_i from the J2 axis:

    t_joint_hold  = g * (m_p * L + sum(m_i * r_i))
    t_joint_peak  = t_joint_hold + J * alpha,  J = m_p * L^2 + sum(m_i * r_i^2),
                    alpha = omega_max / t_accel
    motor side:   t = t_joint * SF / (gear_ratio * efficiency);  rpm = omega_max * ratio

Inputs come from the AR4 research file with sources; t_accel and SF are project parameters.
The existing torque, speed and voltage checks then run unchanged. The 50:1 gearbox stays a
separate line, so the agents keep searching NEMA 23 motors with the existing pipeline.

## 7. Asks for Omar

UI (frontend/):
1. Project switcher: Stretch / AR4 club (`POST /api/jobs` gains optional `project_id`).
2. Project card from `project`: facts with a verified (quote link) or stated badge, criteria
   with the rule reason for each.
3. Risk table from `risk_line`: one row per BOM line, five factor chips, overall level,
   ILLUSTRATIVE badge on Stretch lines.
4. Alternatives per line from `alternative`; recommendations from `recommendation`, ranked.
5. Domestic % only when `criteria.domestic_threshold` is set.

CAD (cad/), he offered any capability needed:
1. `POST /build` gains `robot: "wheeled" | "ar4" | "stretch"` (default wheeled, so nothing
   breaks). `stretch` is an ILLUSTRATIVE Stretch-like body (mobile base, mast, arm) with the
   shoulder motor mount regenerated; the viewer labels it illustrative.
2. For ar4: the arm in context with the J2 motor + gearbox + mount plate, the regenerated mount
   highlighted. Inputs: frame (17/23/34), pilot diameter, bolt spacing, shaft diameter, body
   length. Arm geometry: ar4_ros_driver URDF meshes (repo is MIT; Omar to confirm the meshes'
   licence, since Annin's STLs are non-commercial).
3. Fit result as generic rows, additive next to today's keys:
   `fit_checks: [{name, value, limit, unit, ok}]`, e.g. `j2_envelope` (body length vs turret
   space), `shaft_to_gearbox_bore`. The backend turns each row into a check.

## 8. Core for Tygo

`recommend(line, current: LineRisk, alternatives: list[Alternative]) -> Recommendation` in
backend/app/engineering/recommend.py, pure, rules in section 5. It carries the product's final
decision, so it is the piece Tygo should be able to explain. Failing tests come with the
scaffold. Alternative: Tygo takes `line_risk` (factor levels) instead.

## 9. Schedule (EST, freeze 4:00)

| until | work |
|---|---|
| 10:30 | approval of this doc; research pass 2 running |
| 12:00 | chunk A: Project/Criteria/Fact schemas, project files, INTAKE (Stretch live fetch), CRITERIA rules, arm requirement, `project` event |
| 1:30 | chunk B: risk factors + RISK_BASELINE, alternatives from research, RANK from criteria, RECOMMEND (Tygo core), events |
| 3:00 | chunk C: live AR4 J2 job recorded (Teknic + 2 discovered sites), Stretch intake recorded, CAD ar4 integration |
| 4:00 | replays for both cases, demo script, docs |

## 10. Decisions (recommendation first)

1. Stretch scope: CHANGED BY TYGO to the full deep loop and CAD on an ILLUSTRATIVE shoulder
   actuator. Its requirement uses the public 50 lb (23 kg) max case weight plus illustrative
   arm geometry; every illustrative input is labelled, and the agents' finds are real parts.
   Rejected: risk map only (less to show for the company case).
2. AR4 deep line: J2 motor only, gearbox kept as its own line. Alternative: search geared
   motors as one unit (new agent goal and schema, fewer vendors sell exact matches).
3. Risk overall = worst known factor, no weighted score. Alternative: weighted sum (needs
   weights nobody can source).
4. Club location: Canada (Western, London ON), so the trade factor uses Canadian duty.
   Alternative: a US club (reuses the US tariff research already done).
5. Project facts for Stretch extracted by Flash from official pages and verified by quote.
   Alternative: hand-written facts file with quotes (no live intake on stage).
6. Keep `data/demo_robot.json` and the wheeled job working as-is; the new projects sit next to
   it. Alternative: replace it (less to maintain, breaks Omar's current UI).
7. Core: `recommend()` for Tygo. Alternative: `line_risk()`, or skip core.
