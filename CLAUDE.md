# CLAUDE.md

Source of truth for how to work in this repo. Read this first, then `docs/PRODUCT.md` and `docs/ARCHITECTURE.md`. If this file and the code disagree, say so and ask; do not guess.

## What this project is

A text-to-frame designer for aluminum extrusion (T-slot) frames. The user types a request such as "workbench 1500 x 700 mm, holds 100 kg, lower shelf" and gets a 3D frame, a cut list, a bill of materials with cost, and a load estimate.

## Core design rules

These are product decisions, not suggestions. Changing any of them needs approval.

1. **The LLM only produces the spec.** It turns text into a small validated `FrameSpec`. It never outputs geometry, part counts, prices, or load results.
2. **Everything after the spec is deterministic code.** The same spec always gives the same frame, cut list, and checks.
3. **Load results are estimates and must say so.** They are conservative, use a stated safety factor, and are labelled as estimates everywhere they appear. People will physically build these.
4. **Catalog data is never invented.** Profile properties, part numbers, and prices come from a named source recorded in the catalog file. If a value is missing, leave it missing and flag it.
5. **Units:** millimetres, kilograms, newtons internally. Convert only at the edges (input parsing, display).

## Stack

- Backend: Python 3.11+, FastAPI, Pydantic v2
- Backend tests and checks: pytest, ruff, mypy
- Frontend: Next.js 16 App Router, TypeScript, Tailwind CSS v4, React Three Fiber / drei
- Frontend tests: Vitest + React Testing Library (run from `frontend/`)
- LLM: called only from `src/framegen/parser/` and `src/framegen/suggestions/rank.py`;
  API key from the environment, never from a file in the repo

## Layout

```
CLAUDE.md
README.md
docs/PRODUCT.md        what we are building and for whom
docs/ARCHITECTURE.md   pipeline, modules, data shapes
src/framegen/
  catalog/     load, validate, and version parts data
  spec.py      FrameSpec model
  generate/    spec -> frame (bars, joints)
  checks/      collision, connectivity, load estimate
  outputs/     cut list, bill of materials
  parser/      text -> FrameSpec (LLM, with a rule-based fallback)
  suggestions/ fix candidates (pure code) + LLM ranker
  api.py       FastAPI app
evals/         benchmark prompts, scoring, logged runs
frontend/      Next.js 16 app (current UI)
  app/         App Router pages and layout
  components/  React components (viewer, panel, prompt bar, theme toggle)
  hooks/       useFrameApi, useParseApi, useSuggestApi, useUndo
  lib/         types, examples, coordinates, theme helpers
  __tests__/   Vitest unit tests
tests/         Python backend tests
data/catalog/  versioned catalog files
```

## Commands

Install the backend package and dev tools once:

```
pip install -e ".[dev]"
```

Install the frontend once (from `frontend/`):

```
cd frontend && npm install
```

Then (backend, from repo root):

```
pytest                      # Python tests
ruff check . && mypy src    # lint and types
python -m framegen --width 1500 --depth 700 --height 900             # cut list, no shelf
python -m framegen --width 1500 --depth 700 --height 900 --shelf 300 # cut list, with shelf
python -m evals.run --config rule_based --file dev        # parser eval, dev set
python -m evals.run --config rule_based --file regression # parser eval, regression set
python -m evals.run --config dispatcher --file dev        # full dispatcher (needs ANTHROPIC_API_KEY)
uvicorn framegen.api:app    # local server on :8080; loads .env if present
```

Frontend (from `frontend/`):

```
npm run dev     # dev server on :3000, proxies /frame /parse /suggest to :8080
npm test        # Vitest unit tests
npm run lint    # ESLint (eslint .)
npx tsc --noEmit  # TypeScript type check
npm run build   # production build (also type-checks)
```

Both servers must be running for the UI to work: `uvicorn framegen.api:app` on :8080 and `npm run dev` on :3000.

API endpoints:

```
GET  /frame   width, depth, height, shelf?, series?, load_kg?, centre_legs?
              → bars, cut list, check_report, suggestions
POST /parse   {"text": "<500 chars>"}
              → outcome, spec, error, defaults_applied, parser_used, llm_available
POST /suggest {"spec": FrameSpec, "original_request": str}
              → {"suggestions": [FixCandidate, ...]}
```

## How to work

Before a non-trivial change:

1. Read the relevant code and docs.
2. State the requested outcome in one or two sentences.
3. Name the files and modules likely affected.
4. Give a short plan and wait for a go-ahead if the change touches an approval item below.
5. Implement the smallest change that solves the problem.
6. Run the relevant tests and checks.
7. Verify real behaviour, not just that it compiles: generate a frame, look at the numbers, open the page.
8. Check related functionality for regressions.
9. Summarize: what changed, why, what was tested, what is still uncertain.

Trivial changes (typos, renames, a comment) skip the plan but not the checks.

For bugs: reproduce, investigate, find the root cause, fix, verify. Write the failing test first where practical. Do not change code until the cause is understood.

## Verification, by area

- **Generator:** bar counts and lengths match a hand calculation for at least one simple spec.
- **Checks:** load math is checked against a worked beam-bending example with known numbers.
- **Outputs:** cut list lengths sum to the total bar length in the frame; bill of materials total matches the line items.
- **Parser:** run the eval harness and report the scores before and after.
- **Web page:** open it and look at the frame; a passing test suite is not evidence the page works.

## Needs approval first

- Changing the load-check formula, safety factor, or how estimates are labelled
- Adding or editing catalog data, prices, or their sources
- Changing `FrameSpec` or any other shared data shape
- Adding a dependency
- Deleting files or data
- Anything involving secrets, auth, billing, or deployment
- Architectural changes, or breaking any core design rule above

Small, reversible code changes inside one module do not need approval.

## Do not

- Invent APIs, requirements, catalog values, or product behaviour
- Weaken, skip, or delete tests to make them pass
- Make unrelated refactors alongside a change
- Commit or print secrets
- Use LEGO or any vendor's name or logo in product branding

## Agents

One session by default. Add a separate reviewer only when a change touches the load check or catalog data, where an independent look is worth the overhead.
