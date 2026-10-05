# UI Redesign Plan — Drafting Table

> Note: `docs/design/drafting-table.png` was referenced in the brief but does not exist in the repo.

## Feel

Engineering-drawing aesthetic. Square corners everywhere (radius 0), thin rules, no shadows, no
gradients. Monospace for every number, unit, and label.

---

## Stage 1 — Tokens + Fonts

### CSS variable renames and new values (light mode)

| Old name       | New name       | New value  | Notes                          |
|----------------|----------------|------------|--------------------------------|
| `--bg`         | `--paper`      | `#EEF1F3`  | Page/viewer background         |
| (new)          | `--grid`       | `#D7DEE4`  | Grid lines on viewer + CSS bg  |
| `--surface`    | `--surface`    | `#FFFFFF`  | Panel/column backgrounds       |
| `--text`       | `--ink`        | `#16202A`  | Body text                      |
| `--muted`      | `--muted`      | `#52606D`  | Secondary text (value changes) |
| `--border`     | `--rule`       | `#C9D1D8`  | Lines and borders              |
| `--accent`     | `--accent`     | `#C2410C`  | CTA, active tab underline      |
| `--accent-hover`| `--accent-hover`| `#A4360A` | Hover state                    |
| `--accent-fg`  | `--accent-fg`  | `#FFFFFF`  | Text on accent bg              |
| `--warn`       | `--warn`       | `#8A4B00`  | Warn text (7.3:1 on white)     |
| (new)          | `--warn-bg`    | `#FFF1DC`  | Warn indicator background      |
| `--pass`       | `--pass`       | `#1E7A45`  | Kept (5.0:1) — see note below  |
| `--fail`       | `--fail`       | `#B83A25`  | Kept (5.6:1) — see note below  |
| `--dim`        | `--dim`        | `#5A84C8`  | Kept                           |

**Pass/fail note:** `--fail #B83A25` is a similar hue to the new orange accent `#C2410C`.
Proposal for Stage 3: fail → `#9B1C1C` (dark red, 7.3:1), pass → `#166534` (dark green, 7.3:1).
Needs approval before changing.

### Tailwind @theme inline aliases stay the same

`bg-bg`, `text-text`, `border-border`, etc. keep working because @theme inline still maps
`--color-bg: var(--paper)`, `--color-text: var(--ink)`, `--color-border: var(--rule)`.
No component changes are needed in Stage 1.

New aliases added: `bg-grid` / `text-grid`, `bg-warn-bg` / `text-warn-bg`.

### Dark mode

Variable names updated to match. Existing dark values kept as-is. Dark "blueprint" theme
deferred to Stage 4.

### Fonts

| Old                | New              |
|--------------------|------------------|
| Inter              | IBM Plex Sans    |
| JetBrains Mono     | IBM Plex Mono    |

Both loaded via `next/font/google`; no new npm dependency.
CSS variable names: `--font-ibm-plex-sans`, `--font-ibm-plex-mono`.

### Files changed in Stage 1

- `frontend/app/layout.tsx` — swap font imports and variable names
- `frontend/app/globals.css` — rename vars, update values, add --grid / --warn-bg, update all
  override blocks and @theme inline
- `frontend/components/FrameDesigner.tsx` — one inline `var(--bg)` → `var(--paper)`

---

## Stage 2 — Three-column layout + bottom strip

### Desktop layout (≥1280px / `xl:` breakpoint)

```
┌──────────────────────┬─────────────────────────────┬──────────────────────┐
│ LEFT  340 px         │ CENTER  flex                 │ RIGHT  360 px        │
│ bg-surface           │ bg-paper + CSS grid bg       │ bg-surface           │
├──────────────────────┤                              ├──────────────────────┤
│ [FRAME DESIGNER]     │ [caption strip]              │ TOTAL TO ORDER       │
│ [new design] [theme] │ 1500 × 700 × 900 · 40-series │ $XXX.XX              │
├──────────────────────┤                              │ Bars $xx  Hdw $xx    │
│ [Dimensions ▸]       │ ┌────────────────────────┐  ├──────────────────────┤
│   W/D/H/load/…       │ │  3D viewer (flex-1)    │  │ Parts │ Cut │ Load   │
├──────────────────────┤ │                        │  │ plan  │     │ check  │
│ [thread, scrollable] │ └────────────────────────┘  ├──────────────────────┤
│                      │ ┌────────────────────────┐  │ [tab content,        │
│                      │ │ Govern │ Stress │ Defl  │  │  scrollable]         │
│                      │ │ rail   │ MPa    │ mm    │  │                      │
│                      │ │ ─────  │ Util % │ ───── │  │                      │
│                      │ └────────────────────────┘  │                      │
├──────────────────────┤                              │                      │
│ CHANGE OR DESCRIBE   │ [footer links + disclaimer]  │                      │
│ [input  ] [Send ▶]   │                              │                      │
└──────────────────────┴─────────────────────────────┴──────────────────────┘
```

### Bottom strip cells (4 columns)

Data from `frameData.check_report.load.governing_rail`:

1. **Governing rail** — `governing_rail.role`
2. **Max stress** — `max(distributed, concentrated).bending_stress_mpa` MPa
3. **Max deflection** — `max(distributed, concentrated).deflection_mm` mm
4. **Utilisation** — `governing_rail.utilisation * 100` %

Hidden when no frame is loaded.

### Right column tabs

| Tab        | Content                                              |
|------------|------------------------------------------------------|
| Parts      | CutList, PartsList, cost saving suggestion           |
| Cut plan   | CutPlan component                                    |
| Load check | LoadCheck, structural suggestions                    |

Tab active state: 3 px accent-colored bottom border on the active tab label.

### Left column

- Header strip: sheet label + New design button + ThemeToggle
- Collapsible **Dimensions** block (only when spec is present) — DimensionsForm
- Scrollable thread area — ConversationThread / EmptyState / example chips
- Pinned input at bottom: label "CHANGE OR DESCRIBE", PromptBar with accent Send

### Phone (≤xl, existing layout)

Mobile layout is unchanged in Stage 2. Existing header + viewer + DetailsSheet + ThreadSheet
remain. Stage 4 will rework mobile to: viewer → bottom strip (2×2 grid) → thread + input,
with right column becoming a bottom sheet.

### Files changed in Stage 2

- `frontend/components/FrameDesigner.tsx` — two rendering paths: `xl:flex` desktop three-column,
  `xl:hidden` existing mobile layout; also adds BottomStrip helper and right-panel tab state
- Imports added: `CheckReport`, `CutList`, `CutPlan`, `DimensionsForm`, `LoadCheck`, `PartsList`,
  `Suggestions`, `SuggestionCard`

---

## Stage 3 — Thread, cards, tabs, buttons

- Square corners everywhere (`border-radius: 0`)
- Accent underline tabs (3 px bottom border, no background fill on active)
- Monospace for all numbers, units, labels (already `font-mono` in most places — audit remaining)
- Thread: user bubble right-aligned with `bg-ink text-surface`; assistant card square border
- Cards: square border on `bg-surface`, no rounded corners
- Input: square border, no rounded; Send button is a flat `bg-accent` square
- StatusBadge: update warn to use `bg-warn-bg text-warn`
- Viewer grid: pass `--grid` CSS var to R3F Grid `cellColor`

### Pass/fail color update (needs approval before Stage 3 proceeds)

Proposed: fail → `#9B1C1C`, pass → `#166534`. Confirm before implementing.

---

## Stage 4 — Phone + dark theme

### Phone

Single column: viewer first, 2×2 bottom strip grid, then thread+input.
Right column becomes a bottom sheet (tabbed, same three tabs).

### Dark "blueprint" theme

Not yet designed — defer until Stage 4 begins. Candidate: dark navy background with white rules,
cyan accent. To be decided before implementation.

---

## Checks after each stage

Run from `frontend/`:

```
npx tsc --noEmit
npm run lint
npm test
npm run build
npm run test:e2e   # requires both servers running
```

Review screenshots at 1920×1080, 1280×800, and 375×812 in
`frontend/e2e/screenshots/` before reporting done.

---

## Functionality checklist (all must remain present after every stage)

- [ ] Dimensions form (W / D / H / load / shelf / profile / centre legs / Generate)
- [ ] Structural suggestions under latest assistant card
- [ ] Not-covered list (Load check tab)
- [ ] Concentrated-load warning (Load check tab)
- [ ] Spread-evenly sentence (Load check tab)
- [ ] Hardware assumption note (Parts tab)
- [ ] Cold-start notice (still shown in thread)
- [ ] Footer links (GitHub + disclaimer)
- [ ] Cut list with CSV download
- [ ] Parts list with CSV download
- [ ] Cut plan with scale strips + CSV download
- [ ] ThemeToggle (light/dark, working in both layouts)
- [ ] New design button
- [ ] Example chips on first visit
- [ ] Cut list row hover → highlights bar in 3D viewer
