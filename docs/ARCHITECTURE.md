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
cut list, bill of materials, 3D scene data
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
- **FixCandidate**: fix type (`reduce_span_width`, `reduce_span_depth`, `reduce_load`, `centre_legs`), modified `FrameSpec`, verified `CheckReport`, template `trade_off` string, `resolves` field (which load case the fix targets), and `concentrated_warning_remains`.
- **Bar**: profile id, start point, end point, length (mm), role (leg, centre_leg, rail, brace, shelf support).
- **Joint**: the two bars it connects, position, connector type.
- **Frame**: list of bars, list of joints, the spec it came from.
- **CheckReport**: pass/fail and details for collision, connectivity, and load; the load section carries the safety factor and an "estimate" label.
- **CutList**: bars grouped by profile and length, with quantities.
- **BOM**: line items (part id, description, quantity, unit price, source) and a total.

## Modules

| Module | Responsibility | Depends on | Status |
|---|---|---|---|
| `catalog/` | Load raw parts data, validate it, write a versioned catalog file | nothing | done (v2, one profile) |
| `spec.py` | `FrameSpec` model and validation rules | nothing | done |
| `generate/` | One generator per frame type; spec in, `Frame` out | spec, catalog | done (table) |
| `checks/` | Collision, connectivity, load estimate | catalog | done |
| `outputs/` | Cut list and BOM | catalog | cut list done; BOM not started |
| `parser/` | Text to `FrameSpec`; rule-based + LLM dispatcher | spec | done |
| `suggestions/` | Generate and verify fix candidates for failing load checks; pure code, no LLM | spec, generate, checks | done |
| `suggestions/rank.py` | Rank candidates and write one sentence per fix; only imported by `api.py` | suggestions, anthropic SDK | done |
| `api.py` | `/frame`, `/parse`, and `/suggest` endpoints | all of the above | done |
| `evals/` | Benchmark prompts, scoring, logged runs | parser, generate, checks | done (dev + regression + test prompt sets; harness runs) |
| `web/` | Parse input, Three.js viewer, tables | api | done (parse input, viewer, cut list, checks) |

Dependencies point one way. `generate`, `checks`, `outputs`, and `suggestions/__init__.py` must not import `parser` or `suggestions/rank.py`, so the core runs and tests without an API key.

## Catalog

- Raw source files in `data/catalog/raw/`, each with its origin noted
- The pipeline validates them (required fields, positive dimensions, units) and writes `data/catalog/catalog-vN.json`
- Code reads only the versioned file
- v1: profile geometry only; v2: adds alloy, E, σ_y, I (source: https://8020.net/40-4040.html)

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

When `check_report.load.passed` is `False` (distributed fails) or the concentrated case warns, up to three fix candidates are generated by `src/framegen/suggestions/__init__.py`.

**Trigger:** distributed fails → target distributed pass; only concentrated warns → target concentrated pass.

**Candidate search (closed-form, then verified):**

```
Distributed L_max:   stress → 16·S·σ_allow/F;  defl → sqrt(768·E·I / (1500·F))
Concentrated L_max:  stress → 4·S·σ_allow/F;   defl → sqrt(48·E·I / (300·F))
Load fix:            F_max = spec.target_load_kg / u   (u = governing utilisation)
Centre legs:         set centre_legs=True, verify
```

Every candidate is verified by `generate_table + run_checks`. Only verified passes are offered. Span candidates are rounded down to the nearest 10 mm; load candidates to the nearest 5 kg.

**`GET /frame`** always returns suggestions with template `trade_off` text (no LLM).

**`POST /suggest`** recomputes suggestions server-side, then calls `suggestions/rank.py` if `ANTHROPIC_API_KEY` is set. The LLM may reorder candidates but must not add or drop any. Every number in a sentence must appear verbatim in the candidate's verified data; sentences that fail this guard are replaced with template text.

**Evals:** `evals/suggestions_suite.py` — four signals per case: validity, coverage, count, minimality (the next-step-worse value must fail).

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

## Build order

1. Catalog pipeline ✓
2. Spec and frame generator ✓
3. Checks ✓
4. Cut list and BOM (cut list done)
5. Prompt parser ✓
6. Eval harness ✓
7. Web page ✓
8. Suggestions module ✓
   a. suggestions/__init__.py (pure code) ✓
   b. FrameSpec.centre_legs + generator extension ✓
   c. suggestions/rank.py + POST /suggest ✓
   d. Web Apply button ✓
   e. Suggestions eval suite ✓
9. Release work (hosting, real catalogs, CAD export)
