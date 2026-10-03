# FrameForge

Type a description of the frame you need and get a 3D model, cut list, load estimate, and verified fix suggestions you can take to an aluminum extrusion supplier.

![A passing frame design](docs/images/pass.png)

## What it does

- **Text input** — describe the frame in plain language: `workbench 1500 × 700 mm, holds 100 kg, lower shelf`
- **3D viewer** — interactive model of the generated frame
- **Cut list** — every bar with its exact length, grouped by profile
- **Load estimate** — two beam-bending cases; conservative, with a stated safety factor; labelled as an estimate
- **Fix suggestions** — when a frame fails the load check, up to three verified alternatives (smaller span, reduced load, or centre legs), each confirmed to pass before being shown

![A failing frame design with suggestions](docs/images/fail.png)

## How it works

```
text request → parser → FrameSpec → generate → Frame → checks → cut list + suggestions
```

The LLM is called in two places only: extracting the `FrameSpec` from text, and optionally ranking and wording the fix suggestions. All geometry, bar counts, lengths, load numbers, and check results come from deterministic Python code. The same spec always produces the same frame and the same numbers. This keeps the load estimate auditable and means the core runs and tests without an API key.

## Evaluation

Parser scores on the dev set, latest committed results:

| Config | Total | A | B | C | D | E | F | G | H | I | J |
|---|---|---|---|---|---|---|---|---|---|---|---|
| rule_based | 32 / 40 | 8/8 | 2/2 | 3/3 | 4/4 | 3/3 | 6/6 | 1/4 | 3/8 | 2/2 | — |
| llm only | 35 / 40 | 6/8 | 2/2 | 3/3 | 3/4 | 3/3 | 5/6 | 4/4 | 7/8 | 2/2 | — |
| dispatcher | 46 / 46 | 8/8 | 2/2 | 3/3 | 4/4 | 3/3 | 6/6 | 4/4 | 8/8 | 2/2 | 6/6 |

The rule_based and llm runs used the 40-case dev set (git `c73656c`); the dispatcher run used the 46-case set (git `11bce50`, which added group J). Group scores are pass counts.

**Held-out test:** 18 of 20 on a first run against a set written without access to the parser or the tuning prompts. Both failures were unit-handling bugs in the rule-based parser; both are fixed and covered by new dev cases.

## Load estimate

The load check models each top rail as a simply supported beam and reports two cases:

- **Case (a) — distributed (headline pass/fail):** load spread evenly; each rail carries half the total as a uniform distributed load
- **Case (b) — concentrated (warning):** full load as a point force at midspan of one rail

Constants: safety factor **3.0** applied to yield stress (`σ_allow = σ_y / 3.0`); deflection limit **L / 300**.

This is an estimate, not a structural certification. It does not cover joint failure (T-nut pull-out, bracket shear), column buckling, frame racking, tipping, dynamic or impact loads, shear stress, stress concentrations, shelf weight, or self-weight of bars. See `docs/ARCHITECTURE.md` for the full list. If any required catalog value (E, σ_y, I) is missing, the check returns `not_evaluated` rather than a false pass.

## Run it locally

Requires Python 3.11+ and Node.js.

```bash
# Backend
pip install -e ".[dev]"
uvicorn framegen.api:app        # :8080

# Frontend (second terminal)
cd frontend && npm install
npm run dev                     # :3000, proxies /frame /parse /suggest to :8080
```

LLM features (natural-language input, ranked suggestions) require an Anthropic API key:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

Without the key the rule-based parser handles numeric inputs and `GET /frame` works for direct dimension queries.

## Status and limitations

- One frame type: rectangular table / workbench
- One profile: 40-series aluminum extrusion (40 × 40 mm)
- No real vendor prices yet; BOM structure is in place
- Metric only (mm, kg)
- Right-angle joints only; no angled members, panels, or doors

## Tech stack

- **Backend:** Python 3.11, FastAPI, Pydantic v2
- **Frontend:** Next.js 16 (App Router), TypeScript, Tailwind CSS v4, React Three Fiber / drei
- **LLM:** Claude Haiku via Anthropic SDK — parser and suggestion ranking only
- **Tests:** pytest (backend), Vitest + React Testing Library (frontend)
