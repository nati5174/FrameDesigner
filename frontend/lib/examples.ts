// Example prompts for the empty state.
// Every entry must be parseable by the current rule-based parser.
// Test: python -m pytest tests/ -k parser (or run evals/suggestions_suite.py).

export interface Example {
  prompt: string;
  label: string;
}

export const EXAMPLES: Example[] = [
  {
    prompt: "workbench 1500 x 700 mm, 900 mm tall",
    label: "Standard workbench",
  },
  {
    // This frame fails the load check — suggestions will appear.
    prompt: "bench 3000 x 700 x 900 mm, holds 100 kg",
    label: "Wide bench (shows suggestions)",
  },
  {
    prompt: "standing desk 1200 x 600, lower shelf",
    label: "Standing desk with shelf",
  },
];
