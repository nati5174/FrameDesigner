# Chat interface — approved plan

Status: approved. Stages 1–4 are backend; stages 5–9 are frontend.

---

## Feature goal

Turn the single prompt bar into a persistent conversation. Every request,
refinement, and form edit produces a thread entry. The 3D view and details
panel stay live. The server remains stateless.

---

## Decisions

**1. PartialSpec model.**
A separate `PartialSpec` dataclass in the parser layer (`parser/partial_spec.py`),
with all fields optional. `FrameSpec` (and `TableSpec` / `ShelfUnitSpec`) is not
changed. The API layer mirrors it as a Pydantic `PartialSpecOut` model.

**2. Outcome enum scope.**
The new outcomes (`new_design`, `edit`, `clarify`, `unsupported`) apply to the
`/edit` response only. `/parse` keeps its current outcomes (`spec_valid`,
`spec_invalid`, `not_parsed`) and is preserved for evals.

**3. Frame-type change.**
A message that changes the frame type is returned as `new_design`. Dimensions
(width, depth, height, centre_legs) are carried over. The load field does not
map between types: the documented default for the new type is applied and listed
in `defaults_applied`. The `changes` list includes a `frame_type` entry and
entries for each load field that was reset.

**4. /edit handles every turn.**
`POST /edit` handles every turn including the first (spec = null). The frontend
stops calling `/parse` for user interactions. `/parse` is kept for the eval
harness.

---

## Changes

**5. Request shape.**
```
POST /edit
{
  "text":    string,           // ≤ 500 chars
  "spec":    SpecOut | null,   // current complete design; null on first turn
  "pending": PartialSpec | null  // partial spec from a prior clarify turn
}
```

**6. Edit is the default.**
When a `spec` is present, treat the message as an edit unless it signals a
new design. New-design signals: "start over", "start again", "from scratch",
"new design", "instead build/make/design", or a frame-type word together with
both width and depth in the same message. Everything else sets the fields it
mentions and leaves the rest unchanged.

The response card states whether the turn was read as an edit or a new design
(the `read_as` field).

**7. Form edits bypass /edit.**
The `DimensionsForm` sends the modified spec directly to `POST /frame`. The
thread entry is built in the frontend from the field differences; no server
round-trip through the edit parser.

**8. Unsupported detection runs after the rule parser.**
A message the rule parser successfully interprets as an edit or a design is
never unsupported. "Can it hold 150 kg?" sets `target_load_kg = 150` and
reports the check result; it is not unsupported. If the rule parser returns
`not_matched`, the dispatcher then checks the unsupported keyword list, and
the LLM may also return `unsupported`.

**9. Operation validation.**
Operations are validated before the spec is rebuilt:
- The field must exist on the current frame type.
- `add` is only allowed on numeric fields that currently have a value.
- The resulting spec must pass the normal `TableSpec` / `ShelfUnitSpec`
  validation and sanity limits.
A failed operation returns `spec_invalid` with the reason and changes nothing.

**10. Extended rule-based edit patterns.**
In addition to the basic height/width/depth/load/shelf/centre-legs patterns,
the rule parser handles:
- Depth: "deeper", "shallower"
- Shelf: "raise the shelf to/by N", "lower the shelf to/by N"
- Shelf unit: "add a level at N mm", "remove a level", "N levels" /
  "set to N levels", "N kg per level"

**11. Next-step buttons.**
Each assistant reply card includes 2–3 next-step buttons, chosen by plain
code: verified suggestions (from the `check_report`) when the frame fails or
warns on load; otherwise common edit chips ("make it 100 mm taller",
"add a shelf", "add centre legs"). Buttons are pre-filled prompts that trigger
a new `/edit` call.

**12. Per-turn spec history.**
Each assistant turn stores its spec. Clicking a past turn restores that design
and appends a thread entry saying so. This replaces the single-step undo.

**13. Thread persistence.**
The thread is serialised to `localStorage` on every change and hydrated on
mount. No new dependency. A "New design" button clears both state and storage.

**14. Edit eval suite.**
Separate prompt files and scoring function for the `/edit` endpoint.
Each case: starting spec (or pending partial), text, expected outcome and spec.
Groups: `set`, `add`, `shelf`, `shelf_unit_levels`, `type_change`, `clarify`,
`keep_other_fields`, `spec_invalid` (out-of-range values), `unsupported`,
`load_question`. Scored separately for `rule_based`, `llm`, and `dispatcher`.

**Correction:** an out-of-range value (e.g. height 3000 mm) is `spec_invalid`
with the reason, not `unsupported`. It has its own eval group (`spec_invalid`).

**15. /edit → /frame flow.**
After `/edit` returns a spec, the frontend calls `POST /frame`. The reply
card's status badge comes from that `check_report`.

---

## API shapes

### POST /edit — request

```json
{
  "text":    "<string, ≤500 chars>",
  "spec":    "<SpecOut | null>",
  "pending": "<PartialSpec | null>"
}
```

`PartialSpec` (all fields optional):
```json
{
  "frame_type":        "table" | "shelf_unit" | null,
  "width_mm":          number | null,
  "depth_mm":          number | null,
  "height_mm":         number | null,
  "profile_series":    string | null,
  "shelf_height_mm":   number | null,
  "target_load_kg":    number | null,
  "centre_legs":       bool | null,
  "level_heights_mm":  number[] | null,
  "load_per_level_kg": number | null
}
```

### POST /edit — response

```json
{
  "outcome":          "new_design" | "edit" | "clarify" | "unsupported" | "spec_invalid" | "not_parsed",
  "spec":             "<SpecOut | null>",
  "pending":          "<PartialSpec | null>",
  "changes":          [{"field": string, "old": any, "new": any}],
  "missing":          ["field_name", ...],
  "defaults_applied": ["field=value", ...],
  "read_as":          "edit" | "new_design" | null,
  "parser_used":      "rule_based" | "llm" | "none",
  "llm_available":    bool,
  "error":            string | null
}
```

Field rules:

| Outcome | `spec` | `pending` | `changes` | `missing` | `read_as` | `error` |
|---|---|---|---|---|---|---|
| `new_design` | complete | null | populated when prior spec existed | [] | `"new_design"` | null |
| `edit` | complete | null | populated | [] | `"edit"` | null |
| `clarify` | null | partial | [] | 1–2 field names | null | null |
| `unsupported` | null | null | [] | [] | null | fixed string |
| `spec_invalid` | null | null | [] | [] | null | reason |
| `not_parsed` | null | null | [] | [] | null | message or null |

**Clarify flow:** the client sends the returned `pending` as the next
request's `pending` field. The server merges the new text with the partial;
fields already in `pending` are treated as set.

**Unsupported fixed message:**
> "This tool designs aluminum extrusion frames. It can: set dimensions,
> add a shelf, check load capacity, suggest size or load adjustments.
> It cannot give assembly, fastener, or general engineering advice."

### TypeScript additions (`lib/types.ts`)

```typescript
export interface PartialSpec {
  frame_type?: "table" | "shelf_unit";
  width_mm?: number;
  depth_mm?: number;
  height_mm?: number;
  profile_series?: string;
  shelf_height_mm?: number | null;
  target_load_kg?: number | null;
  centre_legs?: boolean;
  level_heights_mm?: number[] | null;
  load_per_level_kg?: number | null;
}

export interface FieldChange {
  field: string;
  old: number | string | boolean | number[] | null;
  new: number | string | boolean | number[] | null;
}

export interface EditRequest {
  text: string;
  spec: FrameSpec | null;
  pending: PartialSpec | null;
}

export interface EditResponse {
  outcome: "new_design" | "edit" | "clarify" | "unsupported" | "spec_invalid" | "not_parsed";
  spec: FrameSpec | null;
  pending: PartialSpec | null;
  changes: FieldChange[];
  missing: string[];
  defaults_applied: string[];
  read_as: "edit" | "new_design" | null;
  parser_used: "rule_based" | "llm" | "none";
  llm_available: boolean;
  error: string | null;
}

export type AssistantCard =
  | { type: "new_design";   spec: FrameSpec; changes: FieldChange[];
      defaults: string[];   frameData: FrameResponse | null }
  | { type: "edit";         spec: FrameSpec; changes: FieldChange[];
      frameData: FrameResponse | null }
  | { type: "clarify";      pending: PartialSpec; missing: string[] }
  | { type: "unsupported";  message: string }
  | { type: "error";        message: string }
  | { type: "loading" };

export type ThreadEntry =
  | { role: "user";      text: string }
  | { role: "assistant"; card: AssistantCard; spec: FrameSpec | null };
```

---

## Stage plan

| Stage | Name | What ships | New files | Modified files | Gate |
|---|---|---|---|---|---|
| **1** | Edit rule parser | `PartialSpec` dataclass; `POST /edit` with rule-based parser only; operation validation; frame-type migration; unsupported detection after rule step | `parser/partial_spec.py`, `parser/edit_rule.py`, `parser/edit_dispatch.py`, `tests/test_edit_rule.py`, `tests/test_api_edit.py` | `api.py` | `pytest tests/test_edit_rule.py tests/test_api_edit.py` passes; `ruff check . && mypy src` clean |
| **2** | LLM edit parser | LLM edit parser with operations format; wired into `/edit` dispatcher; LLM unsupported; clarify from LLM on first turn | `parser/edit_llm.py`, `tests/test_edit_llm.py` | `parser/edit_dispatch.py` | `pytest tests/test_edit_llm.py` passes (mocked); full test suite clean |
| **3** | Centre legs in new-design parsers | Centre-legs keywords (`centre legs`, `center legs`, `middle legs`, `middle support`) recognised in rule-based and LLM new-design parsers | — | `parser/rule_based.py`, `parser/llm.py` | Eval scores rule_based and dispatcher before + after; no regression |
| **4** | Edit eval suite | Dev and regression prompt sets for `/edit`; `edit_suite.py` scorer; `--config edit` in the harness | `evals/prompts_edit_dev.json`, `evals/prompts_edit_regression.json`, `evals/edit_suite.py` | `evals/run.py` | `python -m evals.run --config edit --file dev` prints per-group scores for rule_based, llm, dispatcher |
| **5** | Frontend thread core | New types; `useEditApi`; `useThread` with per-turn spec storage; `ConversationThread`; all `AssistantCard` sub-components; remove `useUndo` | `hooks/useEditApi.ts`, `hooks/useThread.ts`, `components/thread/ConversationThread.tsx`, `components/thread/AssistantCard.tsx` | `lib/types.ts` | `npm test` passes; thread grows |
| **6** | Next-step buttons | Next-step chips on each card; verified suggestions when check fails/warns; otherwise 2–3 common-edit chips | — | `components/thread/AssistantCard.tsx` | Buttons appear; clicking appends entry and triggers `/edit` + `/frame` |
| **7** | Layout + form sync | 3-column desktop layout; `DimensionsForm` → `POST /frame` directly with thread entry built from diff; click-to-restore; "New design" button | — | `components/FrameDesigner.tsx`, `components/panel/DimensionsForm.tsx`, `components/panel/SidePanel.tsx` | Manual walkthrough: form edit appears in thread; clicking past card restores frame |
| **8** | localStorage | Thread hydrated on mount; written on every change; "New design" clears state + storage | — | `hooks/useThread.ts` | Reload preserves thread |
| **9** | Mobile layout | Expandable thread sheet; slide-up details sheet | `components/thread/ThreadSheet.tsx`, `components/panel/DetailsSheet.tsx` | `components/FrameDesigner.tsx` | Manual test at 375 px |

---

## Edit eval groups (stage 4)

| Group | Cases |
|---|---|
| `set` | height set, width set, depth set, load set, centre_legs set true/false |
| `add` | height +N, width +N, depth −N, load +N |
| `shelf` | add shelf (table), remove shelf, raise shelf, lower shelf |
| `shelf_unit_levels` | add level, remove level, set N levels, set load per level |
| `type_change` | table→shelf_unit carries dimensions, load reset in defaults_applied |
| `clarify` | missing width → ask → second turn supplies it → new_design |
| `keep_other_fields` | edit one field, verify all others unchanged |
| `spec_invalid` | out-of-range value (height 3000 mm), negative result after add |
| `unsupported` | "what bolts", "how do I assemble", "will it hold a lathe" |
| `load_question` | "can it hold 150 kg?" → edit, target_load_kg=150, not unsupported |
| `new_design_signal` | "start over", "instead build a 1000×500", "new shelf unit 800×400" |

---

## Files affected (all stages)

**Backend — new:**
`src/framegen/parser/partial_spec.py`,
`src/framegen/parser/edit_rule.py`,
`src/framegen/parser/edit_dispatch.py`,
`src/framegen/parser/edit_llm.py`,
`tests/test_edit_rule.py`,
`tests/test_api_edit.py`,
`tests/test_edit_llm.py`,
`evals/prompts_edit_dev.json`,
`evals/prompts_edit_regression.json`,
`evals/edit_suite.py`

**Backend — modified:**
`src/framegen/api.py`,
`src/framegen/parser/rule_based.py`,
`src/framegen/parser/llm.py`,
`evals/run.py`

**Frontend — new:**
`hooks/useEditApi.ts`,
`hooks/useThread.ts`,
`components/thread/ConversationThread.tsx`,
`components/thread/AssistantCard.tsx`,
`components/thread/ThreadSheet.tsx`,
`components/panel/DetailsSheet.tsx`

**Frontend — modified:**
`lib/types.ts`,
`components/FrameDesigner.tsx`,
`components/PromptBar.tsx`,
`components/panel/DimensionsForm.tsx`,
`components/panel/SidePanel.tsx`
