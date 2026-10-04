import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SuggestionCard } from "@/components/panel/SuggestionCard";
import type { FixCandidate, FrameSpec, CheckReport } from "@/lib/types";

const SPEC: FrameSpec = {
  frame_type: "table",
  width_mm: 2300,
  depth_mm: 700,
  height_mm: 900,
  shelf_height_mm: null,
  profile_series: "20",
  target_load_kg: 100,
  centre_legs: false,
  level_heights_mm: null,
  load_per_level_kg: null,
};

const REPORT: CheckReport = {
  collision: { passed: true, colliding_pairs: [] },
  connectivity: { passed: true, disconnected_bar_indices: [] },
  load: {
    is_estimate: true,
    safety_factor: 3,
    deflection_limit_fraction: 500,
    status: "evaluated",
    not_evaluated_reason: null,
    governing_rail: null,
    all_rails: [],
    passed: true,
  },
  passed: true,
  leg_check: null,
  tipping: null,
  not_covered: [],
};

const CANDIDATE: FixCandidate = {
  fix_type: "reduce_span_width",
  spec: SPEC,
  check_report: REPORT,
  trade_off: "Reduces width to 2300 mm.",
  resolves: "distributed",
  concentrated_warning_remains: false,
};

describe("SuggestionCard", () => {
  it("renders the fix label", () => {
    render(
      <SuggestionCard
        candidate={CANDIDATE}
        canUndo={false}
        onApply={vi.fn()}
        onUndo={vi.fn()}
      />
    );
    expect(screen.getByText("Reduce width")).toBeInTheDocument();
  });

  it("renders the trade-off text", () => {
    render(
      <SuggestionCard
        candidate={CANDIDATE}
        canUndo={false}
        onApply={vi.fn()}
        onUndo={vi.fn()}
      />
    );
    expect(screen.getByText("Reduces width to 2300 mm.")).toBeInTheDocument();
  });

  it("calls onApply with the candidate when Apply is clicked", () => {
    const onApply = vi.fn();
    render(
      <SuggestionCard
        candidate={CANDIDATE}
        canUndo={false}
        onApply={onApply}
        onUndo={vi.fn()}
      />
    );
    fireEvent.click(screen.getByText("Apply"));
    expect(onApply).toHaveBeenCalledWith(CANDIDATE);
  });

  it("shows Undo button only when canUndo is true", () => {
    const { rerender } = render(
      <SuggestionCard
        candidate={CANDIDATE}
        canUndo={false}
        onApply={vi.fn()}
        onUndo={vi.fn()}
      />
    );
    expect(screen.queryByText("Undo")).not.toBeInTheDocument();

    rerender(
      <SuggestionCard
        candidate={CANDIDATE}
        canUndo={true}
        onApply={vi.fn()}
        onUndo={vi.fn()}
      />
    );
    expect(screen.getByText("Undo")).toBeInTheDocument();
  });

  it("shows 'warn remains' badge when concentrated_warning_remains is true", () => {
    render(
      <SuggestionCard
        candidate={{ ...CANDIDATE, concentrated_warning_remains: true }}
        canUndo={false}
        onApply={vi.fn()}
        onUndo={vi.fn()}
      />
    );
    expect(screen.getByText("warn remains")).toBeInTheDocument();
  });
});
