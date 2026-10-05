// Example prompts for the empty state.
// Every entry must be parseable by the current rule-based parser.
// Test: python -m pytest tests/ -k parser (or run evals/suggestions_suite.py).

import type { FrameSpec } from "@/lib/types";

export interface Example {
  prompt: string;
  label: string;
}

export const EXAMPLES: Example[] = [
  {
    prompt: "workbench 1500 x 700 mm, holds 100 kg",
    label: "Workbench",
  },
  {
    // This frame fails the load check — suggestions will appear.
    prompt: "bench 3000 x 700 x 900 mm, holds 100 kg",
    label: "Wide bench (shows suggestions)",
  },
  {
    prompt: "shelf unit 900 x 400 x 1800, 4 levels, 30 kg per level",
    label: "Shelf unit",
  },
];

/** Default design shown on first visit (no saved thread). */
export const DEFAULT_SPEC: FrameSpec = {
  frame_type: "table",
  width_mm: 1500,
  depth_mm: 700,
  height_mm: 900,
  profile_series: "40-series",
  target_load_kg: 100,
  centre_legs: false,
  shelf_height_mm: null,
  level_heights_mm: null,
  load_per_level_kg: null,
};
