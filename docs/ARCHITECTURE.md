# Architecture

Status: catalog, spec, table generator, cut list, CLI, and checks done.
Update this file as modules are built.

## Pipeline

```
text request
   |  parser (rule-based first; LLM as fallback when ANTHROPIC_API_KEY is set)
   v
FrameSpec  -- validated; retry on failure
   |  generate (deterministic)
   v
Frame      -- bars + joints
   |  checks (deterministic)
   v
CheckReport
   |  outputs
   v
cut list, cut plan, bill of materials, 3D scene data
   |  suggestions (deterministic — template text; no LLM)
   v
FixCandidates  -- up to 3 verified passing specs + check reports + template text
   |  POST /suggest (optional, only calls LLM when ANTHROPIC_API_KEY is set)
   v
ranked candidates with one plain sentence each
```

The LLM is called in two places only: `parser/llm.py` (text → FrameSpec) and `suggestions/rank.py` (ranking + prose). Everything else is plain code. `GET /frame` never calls the LLM.

## Data shapes

- **FrameSpec**: frame type, width, depth, height (mm), target load (kg), options (shelf, casters, `centre_legs`), profile series. `centre_legs: bool = False` — when `True`, two extra legs are placed at mid-width, splitting each width rail and shelf rail into two equal half-spans.
  Sanity limits (named constants in `spec.py`; changing requires approval):

  | Constant | Value | Field |
  |---|---|---|
  | `MAX_WIDTH_MM` | 4 000 mm | `width_mm` |
  | `MAX_DEPTH_MM` | 2 000 mm | `depth_mm` |
  | `MAX_HEIGHT_MM` | 2 500 mm | `height_mm` |
  | `MAX_LOAD_KG` | 2 000 kg | `target_load_kg` |

  A spec outside these ranges is rejected (`spec_invalid`) with the message:
  `<field> <value> exceeds maximum <limit> <unit> — check the units`
- **FixCandidate**: fix type (`reduce_span_width`, `reduce_span_depth`, `reduce_load`, `centre_legs`, `reduce_load_per_level`, `cheaper_profile`), modified `FrameSpec`, verified `CheckReport`, template `trade_off` string, `resolves` field (which load case the fix targets), and `concentrated_warning_remains`.
- **Bar**: profile id, start point, end point, length (mm), role (leg, centre_leg, rail, brace, shelf support).
- **Joint**: the two bars it connects, position, connector type.
- **Frame**: list of bars, list of joints, the spec it came from.
- **CheckReport**: pass/fail and details for collision, connectivity, and load; the load section carries the safety factor and an "estimate" label.
- **CutList**: bars grouped by profile and length, with quantities. Each row carries `cost_usd` and `weight_kg` when catalog pricing is available; totals `total_cost_usd` and `total_weight_kg` are also returned.
- **CutPlanResult**: per-profile bin-packing result. Each `ProfileCutPlan` contains `stock_bars` (each with ordered pieces, used_mm, offcut_mm), `does_not_fit`, `lower_bound_bars`, `is_optimal`, `waste_pct`. Inputs `stock_length_mm` (500–8000 mm) and `kerf_mm` (0–10 mm) are user-supplied. No cost data.
- **BOM**: line items (part id, description, quantity, unit price, source) and a total. (Cut list done; BOM not started.)

## Modules

| Module | Responsibility | Depends on | Status |
|---|---|---|---|
| `catalog/` | Load raw parts data, validate it, write a versioned catalog file | nothing | done (v3, four profiles) |
| `spec.py` | `TableSpec` / `ShelfUnitSpec` models and validation rules | nothing | done |
| `generate/` | One generator per frame type; spec in, `Frame` out | spec, catalog | done (table + shelf unit) |
| `checks/` | Collision, connectivity, load estimate, leg check, tipping | catalog | done |
| `outputs/` | Cut list (with cost and weight); cut plan (FFD + B&B); BOM not started | catalog | cut list + cut plan done |
| `parser/` | Text to `FrameSpec`; rule-based + LLM dispatcher (`/parse`); edit parser (`/edit`) | spec | done |
| `suggestions/` | `suggest_fixes` (structural, ≤3); `suggest_cheaper_profile` (standalone, cost saving) | spec, generate, checks | done |
| `suggestions/rank.py` | Rank candidates and write one sentence per fix; only imported by `api.py` | suggestions, anthropic SDK | done |
| `api.py` | `/frame`, `/parse`, `/suggest`, `/edit`, `/cut-plan` endpoints | all of the above | done |
| `evals/` | Parser eval (`run.py`), edit eval (`edit_suite.py`), suggestions eval (`suggestions_suite.py`) | parser, generate, checks | done |
| `frontend/` | Next.js 16 App Router; chat thread, 3D viewer, spec/cut list/suggestions panel, mobile sheets | api | done (stages 1–9) |

Dependencies point one way. `generate`, `checks`, `outputs`, and `suggestions/__init__.py` must not import `parser` or `suggestions/rank.py`, so the core runs and tests without an API key.

## Catalog

- Raw source files in `data/catalog/raw/`, each with its origin noted
- The pipeline validates them (required fields, positive dimensions, units) and writes `data/catalog/catalog-vN.json`
- Code reads only the versioned file
- v1: profile geometry only; v2: adds alloy, E, σ_y, I (source: 8020.net/40-4040.html)
- v3: four profiles (20/30/40/45-series), adds `price_per_mm`, `mass_per_metre_kg`, `cut_charge_usd` (prices read 2026-10-04, not independently verified — treated as estimates)

### v3 profiles

| Series | I (mm⁴) | price/mm (USD) | mass/m (kg) |
|---|---|---|---|
| 20-series (2020) | 6 826 | 0.0131 | 0.441 |
| 30-series (3030) | 27 221 | 0.0181 | 0.870 |
| 40-series (4040) | 137 870 | 0.0441 | 2.359 |
| 45-series (4545) | 139 604 | 0.0402 | 2.041 |

`cut_charge_usd = 3.00` per unique cut (profile × length combination). Cost row = `total_mm × price_per_mm + qty × cut_charge_usd`.

## Load estimate

The load check is labelled as an estimate everywhere it appears. It models each top rail as a simply supported beam and reports two load cases.

### Constants (named in `checks/__init__.py`; changing either requires approval)

```
SAFETY_FACTOR            = 3.0   (applied to yield stress)
DEFLECTION_LIMIT_DIVISOR = 300   (limit is L / 300)
```

### Symbols and units

| Symbol | Unit | Source |
|---|---|---|
| F | N | target_load_kg × 9.81 |
| L | mm | bar centreline length |
| E | MPa | catalog field `youngs_modulus_mpa` |
| σ_y | MPa | catalog field `yield_strength_mpa` |
| I | mm⁴ | catalog field `moment_of_inertia_mm4` |
| S | mm³ | derived: I / (profile_width_mm / 2) |
| σ_allow | MPa | σ_y / SAFETY_FACTOR |
| δ_allow | mm | L / DEFLECTION_LIMIT_DIVISOR |

### Case (a) — distributed (headline pass/fail)

Assumes the load is spread evenly over the top. Two rails in each direction share the total load equally; each carries F/2 as a uniform load (UDL).

```
w   [N/mm]  = (F/2) / L
M_a [N·mm]  = w × L² / 8
σ_a [MPa]   = M_a / S
δ_a [mm]    = 5 × w × L⁴ / (384 × E × I)
```

Checks: σ_a ≤ σ_allow and δ_a ≤ δ_allow. This is the headline pass/fail.

### Case (b) — concentrated (warning)

Models the worst-case single-point loading: full load F as a point force at midspan of one rail.

```
M_b [N·mm]  = F × L / 4
σ_b [MPa]   = M_b / S
δ_b [mm]    = F × L³ / (48 × E × I)
```

Case (b) is reported alongside case (a) for every top rail. When it fails, a warning is shown. It does not override the headline result. Neither case is universally conservative: (a) is unconservative when loading is concentrated; (b) is unconservative for some off-centre or multi-point patterns.

### Governing rail

The rail with the highest utilisation in case (a) is the governing rail:

```
utilisation = max(σ_a / σ_allow,  δ_a / δ_allow)
```

Using utilisation (not stress alone) prevents missing a rail that governs on deflection.

### Missing catalog values

If any of `youngs_modulus_mpa`, `yield_strength_mpa`, or `moment_of_inertia_mm4` is absent, the load estimate returns `status = "not_evaluated"` and `passed = False`. It never reports a pass with incomplete data.

### Centre-leg geometry (`centre_legs = True`)

Two extra legs (`role = "centre_leg"`) are placed at `x = W/2`, one at each depth face. Each width rail and each shelf rail is split at the centre leg into two half-rails:

```
L_half = (W − 3·P) / 2
```

Validation: `W > 3·P`. For W = 3000, P = 40: four width half-rails of 1440 mm and six legs total (4 corner + 2 centre).

**Load model (conservative):** each half-rail carries the same load as a full rail would — F/2 for the distributed case, F for the concentrated case. Formulas are identical to cases (a) and (b) with `L = L_half`.

**Worked example (3000 × 700 × 900, 40-series, 100 kg, centre_legs = True):**

```
L_half = (3000 − 120) / 2 = 1440 mm
σ_allow = 172.37 / 3 = 57.46 MPa    δ_allow = 1440 / 300 = 4.80 mm
σ = 981 × 1440 / (16 × 6893.5) = 12.81 MPa   δ = 2.01 mm   → PASS
```

Without centre legs the governing span is 2920 mm (δ = 16.73 mm, fails).

### What this estimate does NOT cover

1. Joint failure: T-nut pull-out, bracket shear, bolt torque
2. Leg column buckling under compressive load
3. Frame racking under lateral load
4. Tipping under off-centre load
5. Dynamic loads, impact, vibration, fatigue
6. Shear stress in the profile cross-section
7. Stress concentrations at holes, slots, or notches
8. Shelf load (not added to the top-rail check)
9. Profile damage reducing the effective cross-section
10. Combined vertical and lateral loading
11. Self-weight of bars and any tabletop surface
12. Temperature effects on material properties
13. Uneven floor or soft/pivoting mounts

## Suggestions

### Structural fixes (`suggestions/__init__.py` — `suggest_fixes`)

When `check_report.load.passed` is `False` (distributed fails) or the concentrated case warns, up to three fix candidates are generated.

**Trigger:** distributed fails → target distributed pass; only concentrated warns → target concentrated pass.

**Candidate search (closed-form, then verified):**

```
Distributed L_max:   stress → 16·S·σ_allow/F;  defl → sqrt(768·E·I / (1500·F))
Concentrated L_max:  stress → 4·S·σ_allow/F;   defl → sqrt(48·E·I / (300·F))
Load fix:            F_max = spec.target_load_kg / u   (u = governing utilisation)
Centre legs:         set centre_legs=True, verify
```

Every candidate is verified by `generate_table + run_checks`. Only verified passes are offered. Span candidates are rounded down to the nearest 10 mm; load candidates to the nearest 5 kg.

### Cost suggestion (`suggestions/__init__.py` — `suggest_cheaper_profile`)

Separate from structural fixes. Called directly by `_run_frame()` in `api.py` and returned as `cost_suggestion` (a single `FixCandidate | None`), not in the `suggestions` array.

- Only fires when `check_report.passed == True` (frame currently passes)
- Finds the cheapest catalog profile (by `price_per_mm`) that is cheaper than the current profile and whose frame also passes all checks
- Sets `concentrated_warning_remains = True` if the cheaper profile introduces a new concentrated-load warning not present on the current design
- Never competes with structural fixes for the three-slot limit

**`GET /frame` and `POST /frame`** return `suggestions` (up to 3 structural) and `cost_suggestion` (cheaper profile, or null).

**`POST /suggest`** recomputes structural suggestions server-side, then calls `suggestions/rank.py` if `ANTHROPIC_API_KEY` is set. The LLM may reorder candidates but must not add or drop any. Every number in a sentence must appear verbatim in the candidate's verified data; sentences that fail this guard are replaced with template text.

**Evals:** `evals/suggestions_suite.py` — structural fixes: validity, coverage, count, minimality. Cost suggestion: separate cases testing `suggest_cheaper_profile` directly.

## Evals

- A fixed set of prompts, each with expected dimensions and options
- Scores: valid spec rate, valid frame rate, dimension match rate
- Each run is logged with date, parser version, and model, so runs can be compared

## Parser

`src/framegen/parser/` implements text → `FrameSpec` with three outcomes:

| Outcome | Meaning |
|---|---|
| `spec_valid` | Parsed cleanly; `ParseResult.spec` is set |
| `spec_invalid` | Explicitly bad input; `ParseResult.error` explains why; LLM not tried |
| `not_parsed` | Could not parse; `ParseResult.error` is set if the LLM errored (timeout, network, auth) |

### `ParseResult`

```python
@dataclass
class ParseResult:
    outcome: Literal["spec_valid", "spec_invalid", "not_parsed"]
    spec: FrameSpec | None
    error: str | None
    defaults_applied: list[str]   # e.g. ["height_mm=900", "target_load_kg=100"]
    parser_used: Literal["rule_based", "llm", "none"]
```

### Dispatcher (`parser/__init__.py`)

1. Pre-checks: imperial units → `spec_invalid`; enclosure keywords → `spec_invalid`
2. Rule-based parser
3. If `not_parsed` → LLM parser

### Rule-based parser (`parser/rule_based.py`)

- Extracts numeric tokens (with mm/cm/m/kg unit suffixes, abbreviated or spelled out)
- Assigns tokens to slots (width, depth, height, shelf, load) via nearest-keyword matching
- Positional block (`N × N` or `N × N × N`) assigns W/D/H when no keyword claims them
- **Strict accounting**: any unassigned token → `not_parsed`
- Unitless-small check: bare number < 100 in a dimension slot → `spec_invalid` (ambiguous unit)
- Two-shelf detection → `spec_invalid`
- Defaults: `height_mm=900`, `shelf_height_mm=300` (when shelf keyword present), `target_load_kg=100`
- Width and depth are required; no defaults

### LLM parser (`parser/llm.py`)

- Calls `claude-haiku-4-5-20251001` with a structured system prompt
- Asks for 5 fields; `frame_type` and `profile_series` are set in code
- Strips code fences before JSON parse
- Malformed response → 1 retry (includes error in retry prompt)
- `FrameSpec` validation failure → `spec_invalid` (no retry)
- LLM may return `{"result": "insufficient_information"}` → `not_parsed`
- LLM may return `{"result": "unsupported", "reason": "..."}` → `spec_invalid`
- Client injectable via `llm.set_client()` for test mocking; no live calls in tests
- 10-second timeout per call; network/timeout/auth errors → `not_parsed` with error message (never 500)

### Eval harness (`evals/run.py`)

```
python -m evals.run --config rule_based|llm|dispatcher|all --file dev|regression|test
```

`prompts_test.json` is user-written and gitignored. Create it before running `--file test`.

Reports: overall pass rate, per-group pass rate, per-field pass rate (W/D/H/S/L).
Results committed to `evals/results/`. `prompts_test.json` is user-written and never read during parser work.

## `/edit` endpoint

`POST /edit` is the primary endpoint used by the chat frontend for every turn (first and subsequent). It replaces `/parse` for user interactions; `/parse` is kept for the eval harness.

**Request:**
```json
{ "text": "<≤500 chars>", "spec": "<SpecOut | null>", "pending": "<PartialSpec | null>" }
```

**Response outcomes:**

| Outcome | `spec` | Notes |
|---|---|---|
| `new_design` | complete | First turn or explicit "start over"; dimensions carried over on type change |
| `edit` | complete | One or more fields updated; others unchanged |
| `clarify` | null | One or two fields missing; `pending` partial spec returned for next turn |
| `unsupported` | null | Request outside scope; fixed message |
| `spec_invalid` | null | Out-of-range value; `error` field has reason |
| `not_parsed` | null | Parse failure |

**Parser dispatch:**
1. Rule-based parser (`parser/edit_rule.py`) — handles field-set operations, add/subtract, shelf edits, level edits, profile switches, unsupported keywords
2. If `not_matched` → LLM edit parser (`parser/edit_llm.py`) when `ANTHROPIC_API_KEY` is set
3. Unsupported detection runs after the rule step

After `/edit` returns a spec, the frontend calls `POST /frame` to get bars, cut list, and check report.

**`POST /cut-plan`** accepts `{spec, stock_length_mm, kerf_mm}` and returns a stock-bar cut plan (FFD + branch-and-bound). No LLM. Rate-limited 120/minute. Inputs `stock_length_mm` (500–8000) and `kerf_mm` (0–10) are user-supplied and never stored in the catalog.

## Chat frontend (stages 1–9)

The frontend is a persistent conversation. Each turn appends to a thread; the 3D viewer and details panel stay live.

**Thread state (`hooks/useThread.ts`):**
- Serialised to `localStorage` on every change (loading entries filtered); hydrated on mount
- "New design" button clears both React state and `localStorage`

**Per-turn flow:**
1. User types → `POST /edit` → returns outcome + (spec or pending)
2. If `new_design` or `edit` → `POST /frame` → updates viewer, cut list, check report
3. Each assistant card shows next-step buttons: verified suggestions when load fails/warns, otherwise common edit chips

**Mobile layout (stage 9):**
- `ThreadSheet` (`components/thread/ThreadSheet.tsx`): fixed bottom sheet, collapsed = 48 px handle, expanded = 70 vh
- `DetailsSheet` (`components/panel/DetailsSheet.tsx`): slide-up overlay with dimensions/load/cut list; triggered by a floating button
- Desktop: three-column layout (thread column | viewer | side panel) unchanged

## Build order

1. Catalog pipeline ✓
2. Spec and frame generator ✓
3. Checks ✓
4. Cut list (with cost and weight) ✓ — BOM not started
5. Prompt parser (`/parse`) ✓
6. Eval harness ✓
7. Frontend (Next.js) ✓
8. Suggestions module ✓
   a. `suggestions/__init__.py` — structural fixes ✓
   b. `FrameSpec.centre_legs` + generator extension ✓
   c. `suggestions/rank.py` + `POST /suggest` ✓
   d. Web Apply button ✓
   e. Suggestions eval suite ✓
9. Multi-profile catalog v3 (20/30/40/45-series, pricing) ✓
10. Cost suggestion (`suggest_cheaper_profile`, separate `cost_suggestion` field) ✓
11. Edit parser + `/edit` endpoint ✓
    a. Rule-based edit parser ✓
    b. LLM edit parser ✓
    c. Edit eval suite (dev + regression) ✓
12. Chat frontend (stages 1–9) ✓
    a. Thread core + per-turn spec history ✓
    b. Next-step buttons ✓
    c. Desktop 3-column layout + form sync ✓
    d. localStorage persistence (stage 8) ✓
    e. Mobile sheets — ThreadSheet + DetailsSheet (stage 9) ✓
13. Cut plan (`/cut-plan`, `outputs/cut_plan.py`, frontend "Cut plan" section) ✓
14. Release work (hosting, real catalogs, CAD export)
