# Product

## One line

Describe the frame you need, and get a design you can order and bolt together.

## Problem

Aluminum extrusion (80/20, T-slot) is slotted metal bar that bolts together at right angles. People use it for workbenches, sim racing rigs, 3D printer and CNC enclosures, shelving, and lab or robotics setups. Existing tools (80/20 IdeaBuilder, MISUMI FRAMES, Parker T-Slot Design Architect) are manual: the user places every bar and works out lengths and hardware themselves.

## What the user gets

Input: a plain-language request, for example "workbench 1500 x 700 mm, holds 100 kg, lower shelf, casters".

Output:

1. A 3D model of the frame they can rotate
2. A cut list: every bar with its exact length
3. A bill of materials: brackets, bolts, and estimated cost
4. A load estimate: whether it should hold the requested weight
5. Later: CAD export and shareable links

## Users

- First: hobbyists and makers (sim racing, 3D printing, home workshops)
- Possible later: businesses that design frames often (machine builders, automation shops). This is a different product with exact vendor catalogs and engineering-grade checks.

## Scope for the demo

- Frame types: table/workbench, shelf, enclosure
- One profile family and a small hand-made catalog
- Rectangular frames with right-angle joints only

## Out of scope for now

- Angled or curved members, moving parts, panels and doors
- Real-time vendor pricing and ordering
- Accounts and saved designs
- Certified structural analysis

## Success measures

- Eval harness: share of prompts that give a valid spec, a valid frame, and dimensions matching the request
- After release: people who generate a frame, and people who come back

## Constraints

- Load results are conservative estimates, always labelled as such
- Catalog values come from a named source, never invented
- No vendor or toy brand names or logos in the product's branding

## Open questions

- Which profile series and vendor to model first
- Where real part data and prices will come from before release
- Product name
