# STEP export — implementation plan

Status: PLAN ONLY. Do not implement until approved.

---

## 1. Approach recommendation: Option A — pure-Python STEP writer

**Recommendation: Option A.**

### Evaluation

| | Option A — pure-Python writer | Option B — OCP on server |
|---|---|---|
| Production dependency | None (stdlib only) | `cadquery-ocp` ≈ 130–180 MB installed |
| RAM at runtime | Zero overhead | OCC kernel ≈ 150–200 MB at import, leaving ~300 MB on Render free tier (512 MB total) — dangerously tight |
| Cold-start effect | None | OCC import takes 3–5 s; adds to existing cold-start problem |
| Invalid file risk | Mitigated by read-back tests using OCP as a dev-only dependency | Essentially zero — kernel validates as it writes |
| Complexity | Moderate: ~200-line writer for axis-aligned boxes | Low for the writer; high for the dependency management |

**Why Option A is correct here:**

Every bar in this generator is axis-aligned. Looking at `generate_table` and `generate_shelf_unit`, all bars run exactly along X (width rails), Y (depth rails), or Z (legs). There are no diagonal or compound-angle bars. An axis-aligned rectangular box is the simplest possible solid in STEP — it has a closed-form template with 8 vertices, 12 edges, 6 planes, and 6 faces. A correct Python writer for this case fits in ~200 lines with no special cases.

The risk in Option A is silent geometry errors (wrong face normals, open shell, bad winding). This is fully mitigated by the test strategy in §4: every test case re-imports the file using OCP (dev-only) and asserts that every solid is closed, valid, and has the correct volume. If the writer produces an invalid solid, the test fails loudly.

Option B would require adding ~130–180 MB to the production image, risking OOM kills on Render's free tier, and worsening cold starts. It is not appropriate at this scale.

---

## 2. Geometry rules

### Coordinate system
Identical to the generator and 3D viewer:
- Origin at outer bottom-front-left corner of the frame envelope.
- `+X` width, `+Y` depth, `+Z` up. Units: millimetres.

### Box extents for each bar
The solid for a bar with centreline endpoints `(start, end)` and profile width `P` is the axis-aligned box given by `_bbox(bar, P)` (already implemented in `checks/__init__.py`):

| Bar axis | X extent | Y extent | Z extent |
|---|---|---|---|
| Along X (width rail) | `[start.x, end.x]` | `[cy − P/2, cy + P/2]` | `[cz − P/2, cz + P/2]` |
| Along Y (depth rail) | `[cx − P/2, cx + P/2]` | `[start.y, end.y]` | `[cz − P/2, cz + P/2]` |
| Along Z (leg, centre leg) | `[cx − P/2, cx + P/2]` | `[cy − P/2, cy + P/2]` | `[start.z, end.z]` |

The `_bbox` function already implements exactly this. The STEP writer will use the same six-value tuple `(xmin, xmax, ymin, ymax, zmin, zmax)` to generate each solid.

### Solid naming
Each solid is named `"<role> <length_mm>"` — for example `"leg 900"`, `"top rail width 1420"`, `"level rail depth 320"`. The role string is the bar's `role` attribute unchanged. The length is `round(bar.length_mm)` formatted as an integer.

### Simplified geometry statement
The file header comment and the frontend disclaimer both say:
> Simplified: square cross-section bars without T-slots, end holes, or brackets. For checking fit and layout only.

### Determinism
- No `datetime.now()` in the header. Use the fixed string `'2026-10-04T00:00:00'` (catalog date).
- Entity numbers assigned by a sequential counter that resets to 1 for every file. No random or hash-based IDs.
- Floating-point values written as `f"{v:.6f}"` throughout — six decimal places, no scientific notation.
- Bars iterated in generator order (the order returned by `generate_table` / `generate_shelf_unit`). Generator order is already deterministic.

---

## 3. STEP file structure

### Schema: AP214IS

AP214 is preferred over AP203 because it supports product names (so Fusion 360 and FreeCAD import each solid with a human-readable label) and is universally supported by both target applications.

### File layout

```
ISO-10303-21;
HEADER;
  FILE_DESCRIPTION(('Frame Designer — simplified bar geometry', 'No T-slots or brackets'), '2;1');
  FILE_NAME('frame', '2026-10-04T00:00:00', (''), (''), 'Frame Designer', '', '');
  FILE_SCHEMA(('AP214IS'));
ENDSEC;
DATA;
  [shared direction entities for X, Y, Z axes — 3 × DIRECTION]
  [per solid: ~115 entities — see below]
  [PRODUCT hierarchy: PRODUCT, PRODUCT_DEFINITION_FORMATION,
   PRODUCT_DEFINITION, PRODUCT_DEFINITION_CONTEXT,
   PRODUCT_CONTEXT, APPLICATION_CONTEXT,
   SHAPE_DEFINITION_REPRESENTATION, SHAPE_REPRESENTATION,
   MANIFOLD_SOLID_BREP already counted above,
   GEOMETRIC_REPRESENTATION_CONTEXT,
   REPRESENTATION_RELATIONSHIP for assembly]
ENDSEC;
END-ISO-10303-21;
```

### Entities per box solid (~115 per bar)

For one axis-aligned box `(x0,y0,z0)-(x1,y1,z1)`:

| Entity type | Count | Notes |
|---|---|---|
| CARTESIAN_POINT | 8 | One per corner |
| VERTEX_POINT | 8 | One per corner |
| CARTESIAN_POINT (edge origins) | 12 | Can reuse corner points if same start; emit separately for clarity |
| DIRECTION (edge) | 3 shared | X=(1,0,0), Y=(0,1,0), Z=(0,0,1) — shared globally across all solids |
| VECTOR | 12 | One per edge; magnitude = edge length |
| LINE | 12 | One per edge |
| EDGE_CURVE | 12 | Connects two VERTEXes along a LINE |
| ORIENTED_EDGE | 24 | Each edge used once per adjacent face, with orientation flag |
| EDGE_LOOP | 6 | One per face, 4 ORIENTED_EDGEs each |
| FACE_OUTER_BOUND | 6 | Wraps each EDGE_LOOP |
| CARTESIAN_POINT (face origin) | 6 | Centre of each face plane |
| DIRECTION (normal) | 6 | Outward face normal |
| DIRECTION (x-dir) | 6 | Reference direction on face plane |
| AXIS2_PLACEMENT_3D | 6 | Combines face origin + normal + x-dir |
| PLANE | 6 | ELEMENTARY_SURFACE using AXIS2_PLACEMENT_3D |
| ADVANCED_FACE | 6 | Bounds, surface, orientation flag |
| CLOSED_SHELL | 1 | Lists 6 ADVANCED_FACEs |
| MANIFOLD_SOLID_BREP | 1 | References CLOSED_SHELL |

Total: ~115 entities per box. For 20 bars (4-level shelf unit): ~2 300 entities. File size: ~100–150 KB. No memory or latency concern.

**Face normal convention:** all normals point outward from the solid. Orientation flag on ADVANCED_FACE is `.T.` when the PLANE's normal already points outward (which it does when defined as below), `.F.` otherwise. Since we define each plane normal pointing outward explicitly, all flags are `.T.`.

**Winding order on each face:** EDGE_LOOPs traverse the face boundary counter-clockwise when viewed from outside (i.e. from the outward normal direction). This is the STEP convention. The orientation flag on each ORIENTED_EDGE (`.T.` or `.F.`) selects which traversal direction of the underlying EDGE_CURVE is used; the writer must assign these correctly for each face. The plan specifies the winding assignment per face in the implementation notes below.

### Face winding table for axis-aligned box

For box (x0,y0,z0)-(x1,y1,z1), define 8 corners:
```
P0=(x0,y0,z0)  P1=(x1,y0,z0)  P2=(x1,y1,z0)  P3=(x0,y1,z0)
P4=(x0,y0,z1)  P5=(x1,y0,z1)  P6=(x1,y1,z1)  P7=(x0,y1,z1)
```

12 edge curves (each directed from lower-index to higher-index vertex for consistency):
```
E01: P0→P1  (along X)    E12: P1→P2  (along Y)    E23: P2→P3  (along -X)
E03: P0→P3  (along Y)    E45: P4→P5  (along X)    E56: P5→P6  (along Y)
E67: P6→P7  (along -X)   E47: P4→P7  (along Y)    E04: P0→P4  (along Z)
E15: P1→P5  (along Z)    E26: P2→P6  (along Z)    E37: P3→P7  (along Z)
```

Face windings viewed from outside (counter-clockwise = outward normal by right-hand rule):

| Face | Normal | Winding (corners) | Edges used (orientation) |
|---|---|---|---|
| −Z (z=z0) | (0,0,−1) | P0,P3,P2,P1 | E03.T, E23.F, E12.F, E01.F |
| +Z (z=z1) | (0,0,+1) | P4,P5,P6,P7 | E45.T, E56.T, E67.T, E47.F |
| −Y (y=y0) | (0,−1,0) | P0,P1,P5,P4 | E01.T, E15.T, E45.F, E04.F |
| +Y (y=y1) | (0,+1,0) | P3,P7,P6,P2 | E37.T, E67.F, E26.F, E23.T |
| −X (x=x0) | (−1,0,0) | P0,P4,P7,P3 | E04.T, E47.T, E37.F, E03.F |
| +X (x=x1) | (+1,0,0) | P1,P2,P6,P5 | E12.T, E26.T, E56.F, E15.F |

(Orientation .T. means traverse the edge in its stored direction; .F. means reverse.)

The writer must verify this table against the OCP read-back test before shipping.

### PRODUCT hierarchy (for named bodies in Fusion 360)

Each bar becomes one PRODUCT with a name, wrapped in a minimal PRODUCT_DEFINITION chain:

```
APPLICATION_CONTEXT('core data for automotive mechanical design process')
  ↑ referenced by PRODUCT_CONTEXT and PRODUCT_DEFINITION_CONTEXT

PRODUCT('leg 900', 'leg 900', '', (#product_context))
PRODUCT_DEFINITION_FORMATION('', '', #product)
PRODUCT_DEFINITION('design', '', #pdf, #pdc)
PRODUCT_DEFINITION_SHAPE('', '', #product_definition)
SHAPE_DEFINITION_REPRESENTATION(#pds, #shape_rep)

SHAPE_REPRESENTATION('', (#manifold_solid_brep), #geom_context)
GEOMETRIC_REPRESENTATION_CONTEXT(3)  ← shared across all shapes
```

One set of APPLICATION_CONTEXT + PRODUCT_CONTEXT + PRODUCT_DEFINITION_CONTEXT is shared globally. GEOMETRIC_REPRESENTATION_CONTEXT(3) is shared globally. Each bar gets its own PRODUCT through SHAPE_REPRESENTATION.

For the assembly, either:
- (Simpler) Flat: no NEXT_ASSEMBLY_USAGE_OCCURRENCE; all parts at top level. Fusion 360 and FreeCAD both import this correctly as separate bodies.
- (Richer) Nested: one top-level assembly PRODUCT with NAUO links. Adds ~10 entities per bar.

**Recommend: flat for now.** Fusion 360 imports each SHAPE_REPRESENTATION as a separate body under a single component when there is no assembly structure. This is what the user needs.

---

## 4. Tests

### File: `tests/test_step_export.py`

All geometry tests (volume, overlap, closed/valid) use `OCC.Core.*` from `cadquery-ocp`. These tests are decorated:

```python
occ = pytest.importorskip("OCC.Core.BRep", reason="cadquery-ocp not installed — skipping geometry validation")
```

CI installs `cadquery-ocp` so these tests always run there. Local dev may skip them if the package is not installed.

Pure-Python tests (solid count, bounding box from bbox function, determinism, filename) require no OCP and always run.

---

### Test case 1: 1500 × 700 × 900, 40-series, no shelf, no centre legs

**Hand-computed values:**

Profile width P = 40 mm.

Bars:
| Bar | Role | Length (mm) | Section (mm) | Volume (mm³) |
|---|---|---|---|---|
| 4 × corner leg | leg | 900 | 40×40 | 4 × 1 440 000 = 5 760 000 |
| 2 × width rail | top_rail_width | W−2P = 1420 | 40×40 | 2 × 2 272 000 = 4 544 000 |
| 2 × depth rail | top_rail_depth | D−2P = 620 | 40×40 | 2 × 992 000 = 1 984 000 |

Assertions:
- Solid count: **8**
- Overall bounding box: **x ∈ [0, 1500], y ∈ [0, 700], z ∈ [0, 900]**
  (leg centrelines at P/2=20 → physical extent to 0 and 1500; top rail top face at H = 900 ✓)
- Total volume: **12 288 000 mm³** (= total bar length 7 680 mm × P² = 7 680 × 1 600)
- Each solid: closed shell, zero self-intersections (OCP `BRepCheck_Analyzer`)
- No two solids overlap by more than `_BBOX_EPS` (0.01 mm) in volume
  (Joint corners touch but the bbox overlap check from the collision module reports no overlap > threshold — same condition the generator already guarantees)

---

### Test case 2: 1500 × 700 × 900, 40-series, centre_legs=True

Bars added vs. test 1: 2 centre legs (900 mm); 4 full-width rails replaced by 4 half-width rails each `(W−3P)/2 = (1500−120)/2 = 690 mm`.

| Bar | Count | Length (mm) | Volume per bar (mm³) |
|---|---|---|---|
| Corner legs | 4 | 900 | 1 440 000 |
| Centre legs | 2 | 900 | 1 440 000 |
| Half-width rails | 4 | 690 | 1 104 000 |
| Depth rails | 2 | 620 | 992 000 |

Assertions:
- Solid count: **12**
- Bounding box: **x ∈ [0, 1500], y ∈ [0, 700], z ∈ [0, 900]** (same as test 1)
- Total volume: **15 040 000 mm³** = (6×900 + 4×690 + 2×620) × 1 600 = 9 400 × 1 600
- Each solid closed and valid; no overlaps beyond `_BBOX_EPS`

---

### Test case 3: 4-level shelf unit, 900 × 400 × 1800, 40-series

Spec: `ShelfUnitSpec(width=900, depth=400, height=1800, profile_series="40-series", level_heights_mm=[450,900,1350,1800], load_per_level_kg=30, centre_legs=False)`

P = 40.

| Bar | Count | Length (mm) | Volume per bar (mm³) |
|---|---|---|---|
| Corner legs | 4 | 1800 | 2 880 000 |
| Level width rails | 2 × 4 levels = 8 | W−2P = 820 | 1 312 000 |
| Level depth rails | 2 × 4 levels = 8 | D−2P = 320 | 512 000 |

Assertions:
- Solid count: **20**
- Bounding box: **x ∈ [0, 900], y ∈ [0, 400], z ∈ [0, 1800]**
  (top of highest level rail = H = 1800; leg feet start at 0 ✓)
- Total volume: **26 112 000 mm³** = (4×1800 + 8×820 + 8×320) × 1600 = 16 320 × 1 600
- Each solid closed and valid; no overlaps

---

### Test case 4: 1500 × 700 × 900, 45-series (catch hard-coded P=40)

P = 45.

| Bar | Count | Length (mm) | Volume per bar (mm³) |
|---|---|---|---|
| Corner legs | 4 | 900 | 900 × 45 × 45 = 1 822 500 |
| Width rails | 2 | W−2P = 1410 | 1 410 × 2025 = 2 855 250 |
| Depth rails | 2 | D−2P = 610 | 610 × 2025 = 1 235 250 |

Assertions:
- Solid count: **8**
- Bounding box: **x ∈ [0, 1500], y ∈ [0, 700], z ∈ [0, 900]**
- Total volume: **15 471 000 mm³** = (4×900 + 2×1410 + 2×610) × 2025 = 7 640 × 2 025
- Each solid closed and valid

---

### Additional tests (no OCP needed)

- **Determinism:** calling `export_step(spec, bars, profile)` twice produces byte-identical output.
- **Filename:** `step_filename(spec)` for `width=1500, depth=700, height=900` returns `"frame-1500x700x900.step"`.
- **Header:** output does not contain `datetime.now()` (no real timestamp); contains `'2026-10-04T00:00:00'`.
- **Content-type header on endpoint:** POST /export/step returns `Content-Type: model/step` and `Content-Disposition: attachment; filename="frame-1500x700x900.step"`.

---

## 5. API endpoint

### `POST /export/step`

**Request body** (same `SpecOut` model used by `/frame`):
```json
{"spec": {"frame_type": "table", "width_mm": 1500, "depth_mm": 700, "height_mm": 900,
          "profile_series": "40-series", "target_load_kg": 100, "centre_legs": false,
          "shelf_height_mm": null, "level_heights_mm": null, "load_per_level_kg": null}}
```

**Response:** binary STEP file download.
- `Content-Type: model/step`
- `Content-Disposition: attachment; filename="frame-{W}x{D}x{H}.step"` (integer mm values, no decimals if whole numbers)
- `Content-Length` set
- Body: UTF-8 text (STEP files are ASCII-compatible text)

**Rate limit:** `30/minute` per IP (same key function as other endpoints).

**Error handling:**
- Invalid spec (ValidationError): 400, plain message — same pattern as existing endpoints.
- Unknown profile series: 400, `"unknown series: '99-series'"`.
- Generator error (ValueError): 400, plain message.

**Logging:** logged by the existing `_log_middleware` with `endpoint=/export/step`. `frame_type` set from spec. `outcome` set to `"ok"` on success.

---

## 6. Frontend

### Button placement
"Download 3D model (STEP)" appears in the CutList section alongside the existing "Download cut list (CSV)" button. Same style: `text-xs text-muted underline decoration-dotted hover:text-text`.

### Disclaimer text
One muted line below the button:
```
Simplified: square bars without T-slots or brackets. For checking fit and layout.
```

### Next.js proxy
Add one entry to `next.config.ts`:
```typescript
{ source: "/export/step", destination: `${BACKEND}/export/step` },
```

### Frontend API call
POST to `/export/step` with `{spec}`, trigger a file download via `URL.createObjectURL`. Reuse the pattern from `downloadCutListCsv` in `frontend/lib/csvExport.ts`. New function `downloadStepFile(spec)` in `frontend/lib/stepExport.ts`.

---

## 7. Stage 2 (optional, separate approval): DXF export

Using `ezdxf` (≈ 4 MB installed, pure Python, no system dependency), generate a DXF with three orthographic views — front (XZ), side (YZ), and top (XY) — each with overall dimension annotations using DXF `DIMENSION` entities. Add `ezdxf` to `[project.optional-dependencies] dxf = ["ezdxf>=1.2"]`. The endpoint would be `POST /export/dxf`, returning `model/vnd.dxf`. Views use projected outlines of the bounding box of each bar (no hidden-line removal needed at this complexity level). Suitable for cutting a shelf panel to size or verifying clearances in 2D.

---

## 8. Manual check steps

### Fusion 360

1. Open Fusion 360. Start a new empty design (File → New Design) or open an existing one.
2. File → Import → click "Open from my computer" (or press Ctrl+I). Navigate to `frame-1500x700x900.step` and open it.
3. Fusion may ask "Do you want to import this as a new design?" → click **OK**.
4. After import, the model tree on the left (Browser panel) shows a component. Expand it; you should see **8 Bodies** — each listed with a name like "leg 900", "top rail width 1420", etc.
5. Press **M** (or Inspect → Measure). Click one face to get face dimensions, or click two opposing faces to measure the gap.
6. Expected: face-to-face distance on the long axis = **1500 mm**, on the depth axis = **700 mm**, on the height axis = **900 mm**. Use the outer faces of the corner legs for width and depth; top face of a leg or top rail for height.
7. Confirm all 8 bodies are opaque and closed (no holes or missing faces visible when orbiting).

### FreeCAD

1. Open FreeCAD. File → Import (or Ctrl+I). Select `frame-1500x700x900.step`. Click **Open**.
2. FreeCAD imports into the active document. Switch to the **Part** workbench (dropdown at top-left or View → Workbench → Part).
3. In the **Model** tab (left panel), expand the tree. You should see **8 Shape** items, each named "leg 900" etc.
4. Select a Shape in the tree; its size appears in the **View** tab at the bottom. For a leg: the bounding box should be 40 × 40 × 900 mm.
5. To verify the overall frame size: select all 8 shapes (Ctrl+A), then Part → Part menu → **Bounding Box** (or check Properties). Expected: 1500 × 700 × 900 mm.
6. Alternative: use **Part → Measure Linear** — click a face on one corner leg and the opposite corner leg to read 1500 mm (width), 700 mm (depth).
7. The solids should appear fully opaque with no obvious holes. The frame cross-shape at each joint is visible (rails crossing leg corners) because bars are not trimmed at joints.

---

## 9. Files to add or change

### New files

| File | Purpose |
|---|---|
| `src/framegen/outputs/step_export.py` | Pure-Python STEP writer. `export_step(bars, profile, design_name) → str`. No imports outside stdlib. ~200 lines. |
| `tests/test_step_export.py` | All tests from §4. OCP tests skip gracefully when `cadquery-ocp` not installed. ~150 lines. |
| `frontend/lib/stepExport.ts` | `downloadStepFile(spec)` function. ~30 lines. |

### Changed files

| File | Change |
|---|---|
| `src/framegen/api.py` | Add `POST /export/step` endpoint, rate-limited 30/minute. ~40 lines. |
| `frontend/next.config.ts` | Add `/export/step` proxy rewrite. 1 line. |
| `frontend/components/panel/CutList.tsx` | Add "Download 3D model (STEP)" button + disclaimer below existing CSV button. ~15 lines. |
| `pyproject.toml` | Add `cadquery-ocp` to `[project.optional-dependencies] dev`. 1 line. |

---

## 10. Dependencies

| Package | Where | Size installed | Runtime on Render |
|---|---|---|---|
| None | Production | — | — |
| `cadquery-ocp` (≥ 8.0) | Dev / CI only (`[dev]` extras) | ~130–180 MB | NOT installed on Render |

`cadquery-ocp` is added to `[project.optional-dependencies] dev` alongside existing dev tools (`pytest`, `ruff`, `mypy`, `httpx`). CI must install `pip install -e ".[dev]"` (already the documented setup command) and that is sufficient.

`cadquery-ocp` on Windows ships as a ~46 MB wheel. On Linux (CI / Render) the wheel is similar size. It is only ever imported inside `tests/test_step_export.py` behind `pytest.importorskip`.

---

## 11. What could go wrong

1. **Face normal / winding errors** (highest risk): if any ORIENTED_EDGE orientation flag is wrong, the shell is not correctly oriented; Fusion 360 may import the solid but flip it inside-out, and OCP's `BRepCheck_Analyzer` will report an error. The face winding table in §3 must be tested exhaustively against the OCP read-back test before considering the implementation complete. This is the main reason the test suite exists.

2. **STEP entity-number collisions**: each entity in a STEP DATA section must have a unique `#N` number. If the counter has an off-by-one bug, the file is invalid. Mitigation: the writer uses a single monotonically-increasing counter object passed through every helper; a test asserts that every `#N` in the output is unique.

3. **Fusion 360 PRODUCT hierarchy quirks**: Fusion is known to reject STEP files with malformed product hierarchy while accepting the same body geometry in a flat file. The plan uses the minimal product structure (one PRODUCT per solid, no NAUO assembly). If Fusion rejects this, the fallback is to remove all PRODUCT entities and export only the SHAPE_REPRESENTATION with MANIFOLD_SOLID_BREP — this imports as unnamed bodies but always works. Test manually before declaring done.

4. **FreeCAD STEP importer version differences**: FreeCAD 0.21 and 1.0 use different STEP importers (FreeCAD's own vs. OpenCASCADE via python-occ). Both support ADVANCED_BREP_SHAPE_REPRESENTATION and MANIFOLD_SOLID_BREP. No mitigation needed beyond the format being correct.

5. **AP214IS vs AP214 schema string**: some implementations use `'AP214IS'` and others `'AUTOMOTIVE_DESIGN'`. Fusion 360 accepts both; FreeCAD accepts both. Use `'AP214IS'` as it is the ISO 10303-214 designation.

6. **Large shelf units**: a 3-level × centre-legs shelf unit could have ~28 bars → ~3 200 entities → ~130 KB file. Still trivially small and no memory or latency concern.

7. **cadquery-ocp not available on CI**: if CI doesn't install `.[dev]` correctly, OCP tests are silently skipped rather than loudly failing. Mitigation: add a CI assertion that `cadquery-ocp` is importable (a smoke step before tests run), so a missing install is caught before the test skip goes unnoticed.

8. **Non-integer profile widths**: catalog has P=20, 30, 40, 45 (all integers). All arithmetic results in the bbox function are exact floats (no rounding error for these values). The `f"{v:.6f}"` format will produce clean values like `20.000000`. No mitigation needed.
