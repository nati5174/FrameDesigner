# Parts list plan

Goal: add connecting hardware to the cost total so the quoted price is
close to what an order actually costs.

---

## 1. Scope of the plan

This document covers:
- The proposed catalog-v4 hardware table (for approval before any file is written)
- Joint-counting methodology
- Hand-computed test values for three reference frames
- New API fields and data shapes
- Page changes
- Test plan

Nothing in the load check, parser, generator geometry, or existing catalog
fields changes. The LLM is not involved. All pricing is deterministic.

---

## 2. Joining method chosen (same for all four series)

**One 2-hole inside corner bracket per rail end**, secured with 2 bolts
and 2 T-nuts — one bolt+T-nut into the leg's T-slot, one into the rail's
T-slot.

This is the standard 80/20 external fastening method shown on their
product pages for each series. It is the lightest connection that appears
on every series page; it does not involve drilling.

**Hardware per joint (explicit assumption):**

> 1 bracket + 2 bolts + 2 T-nuts per rail end

---

## 3. Proposed catalog-v4 hardware table

Source: 8020.net product pages, read 2026-10-05.
"automated read, not confirmed by a person."

### Brackets (one per joint)

| Series | Part number | Description | Unit price | Fits | Source URL |
|---|---|---|---|---|---|
| 20-series | 20-4119 | 20 Series 2 Hole Inside Corner Bracket, Al 6063-T6, clear anodize, 20×20×3 mm | $5.15 | 20-2020 | https://8020.net/20-4119.html |
| 30-series | 30-4302 | 30 Series 2 Hole Inside Corner Bracket, Al 6063-T6, clear anodize, 30×30×4 mm | $5.25 | 30-3030 | https://8020.net/30-4302.html |
| 40-series | 40-4302 | 40 Series 2 Hole Inside Corner Bracket, Al 6063-T6, clear anodize, 40×40×6 mm | $5.31 | 40-4040 | https://8020.net/40-4302.html |
| 45-series | 45-4302 | 45 Series 2 Hole Inside Corner Bracket, Al 6063-T6, clear anodize, 45×45×6 mm | $5.40 | 45-4545 | https://8020.net/45-4302.html |

### Bolts (two per joint — one into the leg slot, one into the rail slot)

| Series | Part number | Description | Unit price | Fits | Source URL |
|---|---|---|---|---|---|
| 20-series | 11-5308 | M5×8mm Button Head Socket Cap Screw (BHSCS), steel | $0.53 | 20-series | https://8020.net/11-5308.html |
| 30-series | 11-6312 | M6×12mm Button Head Socket Cap Screw (BHSCS), steel | $0.61 | 30-series | https://8020.net/11-6312.html |
| 40-series | 13-8316 | M8×16mm Button Head Socket Cap Screw (BHSCS), steel | $0.61 | 40-series | https://8020.net/13-8316.html |
| 45-series | 11-8318 | M8×18mm Button Head Socket Cap Screw (BHSCS), steel | $0.48 | 45-series | https://8020.net/11-8318.html |

### T-nuts (two per joint)

| Series | Part number | Description | Unit price | Fits | Source URL |
|---|---|---|---|---|---|
| 20-series | 14122 | M5 Slide-In Economy T-Nut Block, steel | $0.37 | 20-series | https://8020.net/14122.html |
| 30-series | 13117 | 30 Series M6 Standard Drop-In T-Nut, steel | $1.30 | 30-series | https://8020.net/13117.html |
| 40-series | 3838 | M8 Slide-In Economy T-Nut Offset Thread, steel | $0.53 | 40-series | https://8020.net/3838.html |
| 45-series | 13132 | 45 Series M8 Standard Drop-In T-Nut, steel | $1.19 | 45-series | https://8020.net/13132.html |

### Cost per joint

| Series | Bracket | 2 × bolt | 2 × T-nut | Total per joint |
|---|---|---|---|---|
| 20 | $5.15 | $1.06 | $0.74 | **$6.95** |
| 30 | $5.25 | $1.22 | $2.60 | **$9.07** |
| 40 | $5.31 | $1.22 | $1.06 | **$7.59** |
| 45 | $5.40 | $0.96 | $2.38 | **$8.74** |

**No weights are published by 80/20 for these hardware parts.**
Weight remains bars-only until a vendor source is found.

---

## 4. Joint counting

### Rule

A **joint** is one rail-end connection to any leg (corner or centre).
Hardware is counted per joint, not per rail.

```
n_joints = count(bars where role not in {"leg", "centre_leg"}) × 2
```

All non-leg bar roles ("top_rail_width", "top_rail_depth",
"shelf_rail_width", "shelf_rail_depth", "level_rail_width",
"level_rail_depth") each contribute exactly 2 joints: one at each end.
This is read from the generated `bars` list, not computed from a formula
per frame type.

No `Joint` objects exist today. The count is derived from the bar roles
that the generator already assigns.

### Hand-computed test values (all 40-series, cost per joint = $7.59)

#### Test A — 1500 × 700 × 900 table, no shelf, no centre legs

Bars from generator:
- 4 legs (`role="leg"`)
- 2 `top_rail_width`: length = 1500 − 2×40 = 1420 mm
- 2 `top_rail_depth`: length = 700 − 2×40 = 620 mm
- **Total: 8 bars, 4 rails, 8 joints**

Parts list:

| Part | Description | Qty | Unit | Line total |
|---|---|---|---|---|
| 40-4302 | 40 Series 2 Hole Inside Corner Bracket | 8 | $5.31 | $42.48 |
| 13-8316 | M8×16mm BHSCS | 16 | $0.61 | $9.76 |
| 3838 | M8 Slide-In Economy T-Nut | 16 | $0.53 | $8.48 |

Hardware total: **$60.72**

Cost breakdown:
- Bars + cuts: $362.69 (existing, unchanged)
- Hardware: $60.72
- **Total: $423.41**

#### Test B — 1500 × 700 × 900 table WITH centre legs

Bars from generator (`centre_legs=True`, P=40):
- 4 corner legs + 2 centre legs
- 4 half-width rails: length = (1500 − 3×40)/2 = 690 mm (2 per depth face)
- 2 depth rails: length = 620 mm
- **Total: 12 bars, 6 rails, 12 joints**

Parts list:

| Part | Qty | Unit | Line total |
|---|---|---|---|
| 40-4302 | 12 | $5.31 | $63.72 |
| 13-8316 | 24 | $0.61 | $14.64 |
| 3838 | 24 | $0.53 | $12.72 |

Hardware total: **$91.08**

#### Test C — 900 × 400 × 1800 shelf unit, 4 levels, 30 kg/level
Levels at 450, 900, 1350, 1800 mm.

Bars from generator:
- 4 corner legs
- Per level: 2 `level_rail_width` (length=820 mm) + 2 `level_rail_depth` (length=320 mm) = 4 bars
- 4 levels × 4 bars = 16 rail bars
- **Total: 20 bars, 16 rails, 32 joints**

Parts list:

| Part | Qty | Unit | Line total |
|---|---|---|---|
| 40-4302 | 32 | $5.31 | $169.92 |
| 13-8316 | 64 | $0.61 | $39.04 |
| 3838 | 64 | $0.53 | $33.92 |

Hardware total: **$242.88**

---

## 5. Catalog v4

### Structure change

v3 is not touched. v4 is a new file at `data/catalog/catalog-v4.json`
that copies all v3 profile entries and adds a top-level `connectors`
section.

```json
{
  "version": 4,
  "cut_charge_usd": 3.00,
  "source_date": "2026-10-04",
  "source_note": "automated read, not confirmed by a person",
  "connectors": {
    "20-series": {
      "joint_type": "2-hole inside corner bracket",
      "parts_per_joint": [
        {
          "part_number": "20-4119",
          "description": "20 Series 2 Hole Inside Corner Bracket",
          "qty_per_joint": 1,
          "unit_price_usd": 5.15,
          "series": "20-series",
          "source": "80/20",
          "source_url": "https://8020.net/20-4119.html",
          "source_date": "2026-10-05",
          "source_note": "automated read, not confirmed by a person"
        },
        { "part_number": "11-5308", "description": "M5x8mm Button Head Socket Cap Screw", "qty_per_joint": 2, ... },
        { "part_number": "14122",   "description": "M5 Slide-In Economy T-Nut Block",    "qty_per_joint": 2, ... }
      ]
    },
    "30-series": { ... 30-4302, 11-6312, 13117 ... },
    "40-series": { ... 40-4302, 13-8316, 3838  ... },
    "45-series": { ... 45-4302, 11-8318, 13132 ... }
  },
  "profiles": { ... identical to v3 ... }
}
```

### New Python models (additive to `catalog/__init__.py`)

```python
class ConnectorPart(BaseModel):
    model_config = ConfigDict(frozen=True)
    part_number: str
    description: str
    qty_per_joint: int          # 1 for bracket, 2 for bolt, 2 for T-nut
    unit_price_usd: float
    series: str
    source: str
    source_url: str
    source_date: str
    source_note: str

class JointConnector(BaseModel):
    model_config = ConfigDict(frozen=True)
    joint_type: str             # "2-hole inside corner bracket"
    parts_per_joint: list[ConnectorPart]

class Catalog(BaseModel):
    ...                         # all existing fields unchanged
    connectors: dict[str, JointConnector] | None = None  # None for v3
```

`Catalog.version` is checked at load time; a warning is printed when
`connectors` is absent (i.e. when a v3 file is loaded).

The catalog path in `catalog/__init__.py` is updated from v3 to v4 once
the file is approved and written. No other code changes the path.

---

## 6. New output module: `outputs/parts_list.py`

```python
@dataclass(frozen=True)
class PartsListRow:
    part_number: str
    description: str
    qty: int
    unit_price_usd: float
    line_total_usd: float
    source_url: str

@dataclass(frozen=True)
class PartsListResult:
    rows: tuple[PartsListRow, ...]
    hardware_cost_usd: float | None   # None when connectors absent for series
    hardware_priced: bool

def count_joints(bars: list[Bar]) -> int:
    """Number of rail-end joints: every non-leg bar contributes 2."""
    return sum(
        1 for b in bars
        if b.role not in ("leg", "centre_leg")
    ) * 2

def build_parts_list(
    bars: list[Bar],
    connectors: dict[str, JointConnector] | None,
    series: str,
) -> PartsListResult:
    ...
```

Logic:
1. `n = count_joints(bars)`
2. If `connectors` is None or `series` not in `connectors`: return
   `PartsListResult(rows=(), hardware_cost_usd=None, hardware_priced=False)`
3. For each `ConnectorPart` in `connectors[series].parts_per_joint`:
   - `qty = part.qty_per_joint × n`
   - `line_total = qty × part.unit_price_usd`
4. `hardware_cost_usd = sum(line_total for all rows)`
5. Return `PartsListResult(rows=..., hardware_cost_usd=..., hardware_priced=True)`

---

## 7. API changes (`api.py`)

### New fields on the `POST /frame` response (additive only)

```python
class FrameOut(BaseModel):
    # --- existing fields, all unchanged ---
    bars: list[BarOut]
    cut_list: list[CutListRowOut]
    cut_list_total_cost_usd: float | None
    cut_list_total_weight_kg: float | None
    check_report: CheckReportOut
    suggestions: list[FixCandidateOut]
    cost_suggestion: FixCandidateOut | None

    # --- new fields ---
    parts_list: list[PartsListRowOut]      # empty list when hardware not priced
    hardware_cost_usd: float | None        # null when hardware not in catalog for series
    total_cost_usd: float | None           # bars+cuts+hardware; null if either missing
    hardware_priced: bool                  # true when catalog has entries for this series
```

`total_cost_usd`:
- `None` when `cut_list_total_cost_usd` is `None` OR `hardware_cost_usd` is `None`
- Otherwise: `cut_list_total_cost_usd + hardware_cost_usd`

### Cheaper-profile suggestion update

`suggest_cheaper_profile` currently compares `cut_list_total_cost_usd`.

Updated rule:
- When **both** the current profile and the candidate profile have
  `hardware_priced=True`: compare `total_cost_usd`.
- Otherwise: compare `cut_list_total_cost_usd` (existing behaviour).

This protects future profiles that may not have hardware data yet.

---

## 8. Frontend changes

### New TypeScript types (additive, `lib/types.ts`)

```typescript
export interface PartsListRow {
  part_number: string;
  description: string;
  qty: number;
  unit_price_usd: number;
  line_total_usd: number;
  source_url: string;
}

// Added to FrameResponse:
parts_list: PartsListRow[];
hardware_cost_usd: number | null;
total_cost_usd: number | null;
hardware_priced: boolean;
```

### Parts list section in the panel

A new `<CollapsibleSection title="Parts list" defaultOpen={false}>` is
added to `PanelContent` (shared between `SidePanel` and `DetailsSheet`),
below Cut list.

Contents:
- A table with columns: Part, Description, Qty, Unit, Total
- Below the table: cost breakdown block

Cost breakdown display logic:
```
if hardware_priced:
    Bars + cuts:  $362.69
    Hardware:     $60.72
    Total:        $423.41
else:
    Bars + cuts (hardware not priced for this profile): $362.69
```

- Never show hardware as $0.
- When `cut_list_total_cost_usd` is null: no cost block shown (existing
  behaviour unchanged).

The existing "Total" row in the Cut list section keeps showing
`cut_list_total_cost_usd` (bars+cuts only) — it does not change.

---

## 9. "Not covered" list

No change. "Joint failure: T-nut pull-out, bracket shear, bolt torque"
stays in both `_TABLE_NOT_COVERED` and `_SHELF_UNIT_NOT_COVERED`.
Adding brackets to the parts list does not change what the load check
covers.

---

## 10. Tests (`tests/test_parts_list.py`)

All written against the 40-series connector data. Existing tests are not
changed.

```
test_count_joints_table_basic
    Frame: 1500×700×900, no shelf, no centre legs
    Expected: 8 joints

test_count_joints_table_centre_legs
    Frame: 1500×700×900, centre_legs=True
    Expected: 12 joints

test_count_joints_shelf_unit_4_levels
    Frame: 900×400×1800, 4 levels [450,900,1350,1800]
    Expected: 32 joints

test_parts_list_table_basic
    Parts list for Test A (8 joints, 40-series)
    Expected:
      row 0: 40-4302, qty=8,  line=$42.48
      row 1: 13-8316, qty=16, line=$9.76
      row 2: 3838,    qty=16, line=$8.48
      hardware_cost_usd = $60.72
      line totals sum == hardware_cost_usd

test_parts_list_table_centre_legs
    12 joints, 40-series → hardware_cost_usd = $91.08

test_parts_list_shelf_4_levels
    32 joints, 40-series → hardware_cost_usd = $242.88

test_parts_list_missing_hardware
    Connectors = None (or series not in connectors)
    Expected: rows=(), hardware_cost_usd=None, hardware_priced=False

test_parts_list_line_totals_sum_to_hardware_total
    For all three reference frames: sum(row.line_total_usd) == hardware_cost_usd
```

Frontend unit test (`__tests__/CutList.test.tsx` or new
`__tests__/PartsList.test.tsx`): renders parts list rows and cost
breakdown for the Test A values; confirms "hardware not priced" label
when `hardware_priced=False`.

---

## 11. Files changed

| File | Action |
|---|---|
| `data/catalog/raw/hardware-v4.json` | New — raw hardware source |
| `data/catalog/catalog-v4.json` | New — v4 catalog (v3 profiles + hardware) |
| `src/framegen/catalog/__init__.py` | Add `ConnectorPart`, `JointConnector`; add `connectors` field to `Catalog`; update path to v4 |
| `src/framegen/outputs/parts_list.py` | New — `count_joints`, `build_parts_list`, `PartsListRow`, `PartsListResult` |
| `src/framegen/api.py` | Add `parts_list`, `hardware_cost_usd`, `total_cost_usd`, `hardware_priced` to `FrameOut`; call `build_parts_list` in `_run_frame()` |
| `src/framegen/suggestions/__init__.py` | Update `suggest_cheaper_profile` to compare `total_cost_usd` when both profiles have hardware |
| `tests/test_parts_list.py` | New — unit tests listed in §10 |
| `frontend/lib/types.ts` | Add `PartsListRow`; add 4 new fields to `FrameResponse` |
| `frontend/components/panel/SidePanel.tsx` (via `PanelContent`) | Add Parts list collapsible section |
| `frontend/components/panel/DetailsSheet.tsx` | Same (shares `PanelContent`) |
| `frontend/__tests__/PartsList.test.tsx` | New — frontend unit tests |

Files NOT changed: `generate/table.py`, `generate/shelf_unit.py`,
`checks/__init__.py`, `outputs/cut_list.py`, `spec.py`, all parsers,
all eval harnesses, `data/catalog/catalog-v3.json`.

---

## 12. Run order (after catalog approval)

1. Write `data/catalog/raw/hardware-v4.json` and `catalog-v4.json`
2. Add models to `catalog/__init__.py`; run `pytest` — all existing tests pass
3. Add `outputs/parts_list.py`; write and run `tests/test_parts_list.py`
4. Update `api.py`; run `pytest` and `mypy`
5. Update `suggestions/__init__.py`; run `pytest`
6. Run `ruff check .` and `mypy src`
7. Update frontend types and panel; run `npm test` and `npm run build`
8. Run `npm run test:e2e`; review screenshots
9. Update README cost numbers (after approval)

---

## 13. What is not in scope

- Any hardware other than the one bracket + fasteners per joint
- Hardware weight (vendor does not publish it)
- Strength check for the bracket or fasteners (stays in "not covered")
- Profile-specific shelf brackets or gussets
- Any LLM involvement
