# Architecture

Status: first slice complete (catalog, spec, table generator, cut list, CLI).
Update this file as modules are built.

## Pipeline

```
text request
   |  parser (LLM, rule-based fallback)
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
```

The LLM is used in exactly one place: text to `FrameSpec`. Everything else is plain code, so the same spec always gives the same result.

## Data shapes

- **FrameSpec**: frame type, width, depth, height (mm), target load (kg), options (shelf, casters), profile series.
- **Bar**: profile id, start point, end point, length (mm), role (leg, rail, brace, shelf support).
- **Joint**: the two bars it connects, position, connector type.
- **Frame**: list of bars, list of joints, the spec it came from.
- **CheckReport**: pass/fail and details for collision, connectivity, and load; the load section carries the safety factor and an "estimate" label.
- **CutList**: bars grouped by profile and length, with quantities.
- **BOM**: line items (part id, description, quantity, unit price, source) and a total.

## Modules

| Module | Responsibility | Depends on | Status |
|---|---|---|---|
| `catalog/` | Load raw parts data, validate it, write a versioned catalog file | nothing | done (v1, one profile) |
| `spec.py` | `FrameSpec` model and validation rules | nothing | done |
| `generate/` | One generator per frame type; spec in, `Frame` out | spec, catalog | done (table) |
| `checks/` | Collision, connectivity, load estimate | catalog | not started |
| `outputs/` | Cut list and BOM | catalog | cut list done; BOM not started |
| `parser/` | Text to `FrameSpec`; LLM call with validation retry, rule-based fallback | spec | not started |
| `api.py` | One endpoint: text or spec in, full result out | all of the above | not started |
| `evals/` | Benchmark prompts, scoring, logged runs | parser, generate, checks | not started |
| `web/` | Prompt box, Three.js viewer, tables | api | not started |

Dependencies point one way. `generate`, `checks`, and `outputs` must not import `parser`, so the core runs and tests without an API key.

## Catalog

- Raw source files in `data/catalog/raw/`, each with its origin noted
- The pipeline validates them (required fields, positive dimensions, units) and writes `data/catalog/catalog-vN.json`
- Code reads only the versioned file

## Load estimate

- Treats each loaded horizontal bar as a simply supported beam and checks bending stress and deflection against limits
- Uses profile properties from the catalog and a stated safety factor
- Reports the governing bar and the margin
- Labelled as an estimate in the API response and on the page
- The exact formula and safety factor are set when the module is built and need approval to change

## Evals

- A fixed set of prompts, each with expected dimensions and options
- Scores: valid spec rate, valid frame rate, dimension match rate
- Each run is logged with date, parser version, and model, so runs can be compared

## Build order

1. Catalog pipeline
2. Spec and frame generator
3. Checks
4. Cut list and BOM
5. Prompt parser
6. Eval harness
7. Web page
8. Release work (hosting, real catalogs, CAD export)
