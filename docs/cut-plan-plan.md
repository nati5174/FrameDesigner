# Cut plan — implementation plan

Status: ready to implement pending approval of hand calculation.

## Hand calculation (reference table, no shelf)

Spec: 1500 × 700 × 900 mm, 40-series (profile width P = 40 mm).
Cut list:
- 2 × 1420 mm  (top_rail_width = 1500 − 2×40)
- 4 × 900 mm   (legs)
- 2 × 620 mm   (top_rail_depth = 700 − 2×40)

Stock = 3000 mm, kerf = 3 mm.
Convention: each piece consumes `length + kerf` mm of stock.

FFD sorted descending: 1420, 1420, 900, 900, 900, 900, 620, 620

| Bar | Pieces placed | Piece mm | Kerfs | Used | Offcut |
|-----|---------------|----------|-------|------|--------|
| 1   | 1420, 1420    | 2840     | 6     | 2846 | 154    |
| 2   | 900, 900, 900 | 2700     | 9     | 2709 | 291    |
| 3   | 900, 620, 620 | 2140     | 9     | 2149 | 851    |

Total piece material = 7680 mm
Total + kerfs = 7680 + 8 × 3 = 7704 mm
Lower bound = ceil(7704 / 3000) = ceil(2.568) = 3 → "fewest bars possible"

Matches the expected output exactly.

## Additional hand calculations for test cases

### With shelf (1500 × 700 × 900, shelf_height_mm=300)

Cut list: 4 × 1420, 4 × 900, 4 × 620 (12 pieces, 11760 mm total)

FFD sorted: 1420 ×4, 900 ×4, 620 ×4

FFD result (5 bars):

| Bar | Pieces                | Used | Offcut |
|-----|-----------------------|------|--------|
| 1   | 1420, 1420            | 2846 | 154    |
| 2   | 1420, 1420            | 2846 | 154    |
| 3   | 900, 900, 900         | 2709 | 291    |
| 4   | 900, 620, 620, 620    | 2772 | 228    |
| 5   | 620                   | 623  | 2377   |

Total + kerfs = 11760 + 12×3 = 11796 mm
Lower bound = ceil(11796 / 3000) = ceil(3.932) = 4

FFD gives 5 bars; lower bound is 4. Branch-and-bound post-pass finds the 4-bar optimum:
each stock bar holds one 1420, one 900, and one 620 piece.
1420+3 + 900+3 + 620+3 = 2949 mm, offcut = 51 mm per bar.
Total offcut = 4 × 51 = 204 mm, waste = 204/12000 × 100 = 1.7%.
is_optimal = True (plan count == lower bound).

### Piece longer than stock

Stock = 500 mm, kerf = 3 mm, piece = 600 mm.
600 > 500 → placed in `does_not_fit`; no stock bars opened for it.

### Kerf = 0

Stock = 3000 mm, kerf = 0.
Bar 1: 1420 + 1420 = 2840, offcut = 160.
Bar 2: 900 + 900 + 900 = 2700, offcut = 300.
Bar 3: 900 + 620 + 620 = 2140, offcut = 860.
Lower bound = ceil(7680 / 3000) = ceil(2.56) = 3 → "fewest bars possible"

### True minimum above lower bound (B&B proves optimality)

Stock = 1000 mm, kerf = 0.
Pieces (synthetic): 4 × 600 mm, 2 × 500 mm.
Total = 3400 mm. Lower bound = ceil(3400/1000) = 4.

Can 4 bins work? Each bin holds 1000 mm. 600 + 500 = 1100 > 1000 (cannot share a bin).
600 + 600 = 1200 > 1000. 500 + 500 = 1000 (fits). So the four 600-mm pieces each need
their own bin, and the two 500-mm pieces go together in one bin: 5 bins minimum.

B&B exhausts the search and confirms 5 is optimal. is_optimal = True.
Label: "fewest bars possible" (search proved nothing better exists).

### FFD sub-optimal, B&B finds optimum, and node-limit path

The shelf case exercises all three:
- `_ffd` alone → 5 bars
- full `plan_cuts` → 4 bars, is_optimal=True
- `plan_cuts(..., _node_limit=1)` → 5 bars, is_optimal=False ("may not be the minimum")

---

## Files affected

### New
- `src/framegen/outputs/cut_plan.py` — FFD algorithm, data classes
- `tests/test_cut_plan.py` — unit tests
- `frontend/components/panel/CutPlan.tsx` — UI section
- `frontend/hooks/useCutPlan.ts` — fetch hook for POST /cut-plan

### Modified
- `src/framegen/api.py` — add POST /cut-plan endpoint
- `frontend/components/panel/SidePanel.tsx` — add CutPlan section below Parts list
- `frontend/lib/types.ts` — add CutPlanRequest / CutPlanResponse types
- `frontend/lib/csvExport.ts` — add buildCutPlanCsv / downloadCutPlanCsv
- `README.md` — add "Cut plan" bullet
- `docs/ARCHITECTURE.md` — new module row, new endpoint

---

## 1. Backend: `src/framegen/outputs/cut_plan.py`

```python
@dataclass(frozen=True)
class CutPlanPiece:
    length_mm: float
    label: str          # role of the bar, e.g. "leg", "top_rail_width"

@dataclass(frozen=True)
class StockBarPlan:
    pieces: tuple[CutPlanPiece, ...]
    used_mm: float      # sum of (length + kerf) for each piece
    offcut_mm: float    # stock_length - used_mm

@dataclass(frozen=True)
class ProfileCutPlan:
    profile_id: str
    stock_bars: tuple[StockBarPlan, ...]
    does_not_fit: tuple[CutPlanPiece, ...]
    total_stock_bars: int
    total_offcut_mm: float
    waste_pct: float
    lower_bound_bars: int
    is_optimal: bool    # total_stock_bars == lower_bound_bars

@dataclass(frozen=True)
class CutPlanResult:
    profiles: tuple[ProfileCutPlan, ...]
    stock_length_mm: float
    kerf_mm: float
```

**Algorithm (`plan_cuts`):**
1. Receive `bars: list[Bar]`, `stock_length_mm`, `kerf_mm`.
2. Group bars by `profile_id`.
3. For each profile group, sort pieces descending by `length_mm`.
4. For each piece: find the first open stock bar where `piece.length_mm + kerf_mm ≤ remaining`; if none, open a new bar. If `piece.length_mm > stock_length_mm`, put in `does_not_fit`.
5. Per bar: `used_mm = sum(p.length_mm + kerf_mm for p in pieces)`, `offcut_mm = stock_length_mm - used_mm`.
6. Profile totals: `total_offcut_mm = sum(b.offcut_mm for b in stock_bars)`.
   `waste_pct = 100 × total_offcut_mm / (total_stock_bars × stock_length_mm)` — 0 when no stock bars.
7. Lower bound: `total_used = sum(p.length_mm + kerf_mm for p in all_pieces)`;
   `lower_bound_bars = ceil(total_used / stock_length_mm)`.
8. `is_optimal = total_stock_bars == lower_bound_bars`.

**Input validation** (raise `ValueError` with clear message):
- `stock_length_mm` not in [500, 8000]
- `kerf_mm` not in [0, 10]

---

## 2. API: `POST /cut-plan`

```
POST /cut-plan
Rate limit: 120/minute (same as /frame)
Logging: endpoint, status, latency_ms (no LLM)
```

Request body:
```json
{
  "spec": SpecOut,
  "stock_length_mm": 3000.0,
  "kerf_mm": 3.0
}
```

Response:
```json
{
  "profiles": [
    {
      "profile_id": "40-4040",
      "stock_bars": [
        {
          "pieces": [{"length_mm": 1420, "label": "top_rail_width"}, ...],
          "used_mm": 2846,
          "offcut_mm": 154
        },
        ...
      ],
      "does_not_fit": [],
      "total_stock_bars": 3,
      "total_offcut_mm": 1296,
      "waste_pct": 14.4,
      "lower_bound_bars": 3,
      "is_optimal": true
    }
  ],
  "stock_length_mm": 3000,
  "kerf_mm": 3
}
```

The endpoint:
1. Reconstructs `TableSpec` or `ShelfUnitSpec` from `SpecOut` (same pattern as `post_frame`).
2. Calls `generate_table` or `generate_shelf_unit` to get bars.
3. Calls `plan_cuts(bars, stock_length_mm, kerf_mm)`.
4. Serialises and returns.

No LLM is called. The frame generation is repeated here (not cached) because this is a stateless API.

---

## 3. Frontend

### `frontend/lib/types.ts`

Add:
```ts
export interface CutPlanPiece {
  length_mm: number;
  label: string;
}
export interface StockBarPlan {
  pieces: CutPlanPiece[];
  used_mm: number;
  offcut_mm: number;
}
export interface ProfileCutPlan {
  profile_id: string;
  stock_bars: StockBarPlan[];
  does_not_fit: CutPlanPiece[];
  total_stock_bars: number;
  total_offcut_mm: number;
  waste_pct: number;
  lower_bound_bars: number;
  is_optimal: boolean;
}
export interface CutPlanResponse {
  profiles: ProfileCutPlan[];
  stock_length_mm: number;
  kerf_mm: number;
}
```

### `frontend/hooks/useCutPlan.ts`

```ts
function useCutPlan(spec: FrameSpec | null)
  → { result, loading, error, stockLength, setStockLength, kerf, setKerf, fetch }
```

- State: `stockLength` (default 3000), `kerf` (default 3), `result | null`, `loading`, `error`.
- `fetch()` calls `POST /cut-plan` with current inputs.
- Auto-fetches when spec changes (if user has previously fetched, i.e. section is open).

### `frontend/components/panel/CutPlan.tsx`

Structure:
```
<CollapsibleSection title="Cut plan" defaultOpen={false}>
  <CutPlan spec={spec} />
</CollapsibleSection>
```

Inside the component:
1. Two labelled inputs (number inputs, clamped to limits):
   - Stock length: 500–8000 mm, default 3000, step 100
   - Kerf: 0–10 mm, default 3, step 0.5
   - Below each: small muted caption "your value; check your supplier and saw"
2. "Calculate" button (or auto-recalculate on blur).
3. When result available:
   - Summary line: "N stock bar(s) to buy · X% waste · [fewest bars possible | may not be the minimum]"
   - If any `does_not_fit`: warning line listing the oversized pieces.
   - For each profile (usually one), per stock bar: a horizontal scale strip.
     - Container: `w-full h-8 rounded overflow-hidden flex` (phone-friendly).
     - Each piece: a colored block, width proportional to `length_mm / stock_length_mm`.
     - Kerf: a thin dark sliver between pieces, width proportional to `kerf_mm / stock_length_mm` (omit if kerf = 0 or too small to see).
     - Offcut: a lighter/hatched block for the remainder.
     - Tooltip or label on each piece: length and role.
   - "Download cut plan (CSV)" button.
4. Note: "Each piece uses its length plus one kerf (saw blade width)."

### `frontend/lib/csvExport.ts`

Add `buildCutPlanCsv` / `downloadCutPlanCsv`:
- Same comment header as cut list / parts list.
- One section per profile.
- Columns: `stock_bar`, `piece_index`, `length_mm`, `label`, `offcut_mm`.
- Summary row per profile: total bars, total offcut, waste %.
- Footer note: stock length, kerf used.

### `frontend/components/panel/SidePanel.tsx`

Add after the Parts list `CollapsibleSection`:
```tsx
{spec && frameData && (
  <CollapsibleSection title="Cut plan" defaultOpen={false}>
    <CutPlan spec={spec} />
  </CollapsibleSection>
)}
```

---

## 4. Tests

### `tests/test_cut_plan.py`

| Test | Spec / input | What is checked |
|------|-------------|-----------------|
| `test_reference_no_shelf` | 1500×700×900, stock 3000, kerf 3 | 3 bars; bar contents and lengths as above; is_optimal=True |
| `test_reference_bar1` | same | pieces=[1420,1420], used=2846, offcut=154 |
| `test_reference_bar2` | same | pieces=[900,900,900], used=2709, offcut=291 |
| `test_reference_bar3` | same | pieces=[900,620,620], used=2149, offcut=851 |
| `test_with_shelf_bar_count` | 1500×700×900 shelf=300, stock 3000, kerf 3 | 5 bars; is_optimal=False |
| `test_with_shelf_lower_bound` | same | lower_bound_bars=4 |
| `test_piece_longer_than_stock` | one 600 mm piece, stock 500 | does_not_fit=[600]; stock_bars=[] |
| `test_kerf_zero` | 1500×700×900, stock 3000, kerf 0 | 3 bars, used/offcut consistent (bar1: used=2840, offcut=160) |
| `test_invalid_stock_too_small` | stock=499 | ValueError |
| `test_invalid_stock_too_large` | stock=8001 | ValueError |
| `test_invalid_kerf_negative` | kerf=-1 | ValueError |
| `test_invalid_kerf_too_large` | kerf=11 | ValueError |
| `test_waste_pct` | reference no shelf | waste_pct ≈ (1296/9000)×100 = 14.4 |
| `test_api_cut_plan` | POST /cut-plan with 1500×700×900 | 200; profiles non-empty |

---

## 5. README and ARCHITECTURE updates

### README

Under "What it does", add after the CSV export bullet:
```
- **Cut plan** — given your stock bar length and saw kerf, shows how many stock bars to buy
  and which pieces to cut from each, drawn to scale; includes a CSV export.
```

### ARCHITECTURE.md

In the Modules table, add:
```
| `outputs/cut_plan.py` | First-fit decreasing bin-pack: bars → stock bar plan | generate | new |
```

In the Build order list, add under step 12:
```
13. Cut plan (`/cut-plan`, `outputs/cut_plan.py`, frontend section) — in progress
```

Update the pipeline comment to include `cut plan` after `cut list, bill of materials`.

---

## 6. Verification checklist (from CLAUDE.md)

- [ ] `ruff check . && mypy src` pass
- [ ] `pytest` passes (first run, before code)
- [ ] Implement
- [ ] `pytest` passes (second run, after code)
- [ ] Frontend unit tests pass (`npm test`)
- [ ] `npx tsc --noEmit` passes
- [ ] `npm run lint` passes
- [ ] `npm run build` passes
- [ ] `npm run test:e2e` passes; review screenshots in `frontend/e2e/screenshots/`

---

## Open questions (none — all resolved by spec)

- Stock prices: explicitly excluded. No cost shown on cut plan.
- BOM integration: out of scope for this change.
- Multi-profile frames: the algorithm handles each profile_id independently; the shelf case uses only one profile.
