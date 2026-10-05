import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AssistantCard } from "@/components/thread/AssistantCard";
import type { AssistantCard as AssistantCardType, CheckReport, FrameResponse, FrameSpec } from "@/lib/types";

const SPEC: FrameSpec = {
  frame_type: "table",
  width_mm: 1500,
  depth_mm: 700,
  height_mm: 900,
  profile_series: "40-series",
  shelf_height_mm: null,
  target_load_kg: 100,
  centre_legs: false,
  level_heights_mm: null,
  load_per_level_kg: null,
};

describe("AssistantCard loading", () => {
  it("shows spinner and Thinking text", () => {
    const card: AssistantCardType = { type: "loading" };
    render(<AssistantCard card={card} spec={null} />);
    expect(screen.getByText("Thinking…")).toBeInTheDocument();
  });
});

describe("AssistantCard new_design", () => {
  it("shows New design badge", () => {
    const card: AssistantCardType = {
      type: "new_design",
      spec: SPEC,
      changes: [{ field: "width_mm", old: 800, new: 1500 }],
      defaults: ["height_mm=900"],
      frameData: null,
    };
    render(<AssistantCard card={card} spec={SPEC} />);
    expect(screen.getByTestId("card-badge")).toHaveTextContent("New design");
  });

  it("formats defaults as plain words (Bug 5)", () => {
    const card: AssistantCardType = {
      type: "new_design",
      spec: SPEC,
      changes: [],
      defaults: ["height_mm=900"],
      frameData: null,
    };
    render(<AssistantCard card={card} spec={SPEC} />);
    // Must show plain-word label, NOT the raw "field_name=value" string
    expect(screen.getByText(/Height 900 mm \(default\)/)).toBeInTheDocument();
    expect(screen.queryByText(/height_mm=900/)).not.toBeInTheDocument();
  });

  it("shows dimension summary for non-latest new_design card (Bug 6)", () => {
    const card: AssistantCardType = {
      type: "new_design",
      spec: SPEC,
      changes: [],
      defaults: [],
      frameData: null,
    };
    // Non-latest cards render a compact one-liner with the dimensions
    render(<AssistantCard card={card} spec={SPEC} isLatest={false} />);
    expect(screen.getByText("1500 × 700 × 900 mm")).toBeInTheDocument();
  });

  it("calls onRestore when Restore is clicked", () => {
    const onRestore = vi.fn();
    const card: AssistantCardType = {
      type: "new_design",
      spec: SPEC,
      changes: [],
      defaults: [],
      frameData: null,
    };
    render(<AssistantCard card={card} spec={SPEC} onRestore={onRestore} />);
    fireEvent.click(screen.getByText("Restore"));
    expect(onRestore).toHaveBeenCalledWith(SPEC);
  });
});

describe("AssistantCard edit", () => {
  it("shows Updated badge", () => {
    const card: AssistantCardType = {
      type: "edit",
      spec: SPEC,
      changes: [{ field: "height_mm", old: 900, new: 1100 }],
      frameData: null,
    };
    render(<AssistantCard card={card} spec={SPEC} />);
    expect(screen.getByTestId("card-badge")).toHaveTextContent("Updated");
  });

  it("shows changed fields with old and new values", () => {
    const card: AssistantCardType = {
      type: "edit",
      spec: SPEC,
      changes: [{ field: "height_mm", old: 900, new: 1100 }],
      frameData: null,
    };
    render(<AssistantCard card={card} spec={SPEC} />);
    // Must show "Height 900 mm → 1100 mm", not just "height changed"
    expect(screen.getByText(/Height 900 mm → 1100 mm/)).toBeInTheDocument();
    expect(screen.queryByText(/height changed/)).not.toBeInTheDocument();
  });
});

describe("AssistantCard clarify", () => {
  it("shows missing field names", () => {
    const card: AssistantCardType = {
      type: "clarify",
      pending: {},
      missing: ["depth_mm"],
    };
    render(<AssistantCard card={card} spec={null} />);
    expect(screen.getByText(/More information needed/)).toBeInTheDocument();
    expect(screen.getByText(/depth/)).toBeInTheDocument();
  });
});

describe("AssistantCard unsupported", () => {
  it("renders the message", () => {
    const card: AssistantCardType = {
      type: "unsupported",
      message: "This tool cannot give assembly advice.",
    };
    render(<AssistantCard card={card} spec={null} />);
    expect(
      screen.getByText("This tool cannot give assembly advice.")
    ).toBeInTheDocument();
  });
});

const PASSING_REPORT: CheckReport = {
  collision: { passed: true, colliding_pairs: [] },
  connectivity: { passed: true, disconnected_bar_indices: [] },
  load: {
    is_estimate: true, safety_factor: 3, deflection_limit_fraction: 300,
    status: "evaluated", not_evaluated_reason: null,
    governing_rail: null, all_rails: [], passed: true,
  },
  passed: true,
  leg_check: null,
  tipping: null,
  not_covered: [],
};

const FRAME_DATA_PASS: FrameResponse = {
  bars: [], cut_list: [], cut_list_total_cost_usd: null, cut_list_total_weight_kg: null,
  check_report: PASSING_REPORT, suggestions: [], cost_suggestion: null,
  parts_list: [], hardware_cost_usd: null, hardware_weight_kg: null,
  total_cost_usd: null, total_weight_kg: null, hardware_priced: false,
};

const CONCENTRATED_FAIL_REPORT: CheckReport = {
  collision: { passed: true, colliding_pairs: [] },
  connectivity: { passed: true, disconnected_bar_indices: [] },
  load: {
    is_estimate: true, safety_factor: 3, deflection_limit_fraction: 300,
    status: "evaluated", not_evaluated_reason: null,
    governing_rail: {
      bar_index: 0, role: "top_rail_width", span_mm: 1500,
      allowable_stress_mpa: 90, deflection_limit_mm: 5,
      utilisation: 0.8, passed: true,
      distributed: { moment_n_mm: 1000, bending_stress_mpa: 20, deflection_mm: 3, stress_passed: true, deflection_passed: true, passed: true },
      concentrated: { moment_n_mm: 5000, bending_stress_mpa: 100, deflection_mm: 6, stress_passed: false, deflection_passed: false, passed: false },
    },
    all_rails: [], passed: true,
  },
  passed: true,
  leg_check: null,
  tipping: null,
  not_covered: [],
};

const FAILING_REPORT: CheckReport = {
  collision: { passed: true, colliding_pairs: [] },
  connectivity: { passed: true, disconnected_bar_indices: [] },
  load: {
    is_estimate: true, safety_factor: 3, deflection_limit_fraction: 300,
    status: "evaluated", not_evaluated_reason: null,
    governing_rail: null, all_rails: [], passed: false,
  },
  passed: false,
  leg_check: null,
  tipping: null,
  not_covered: [],
};

describe("AssistantCard load-check status (Bug 4)", () => {
  it("shows Pass badge when load passes", () => {
    const card: AssistantCardType = {
      type: "edit",
      spec: SPEC,
      changes: [],
      frameData: { ...FRAME_DATA_PASS },
    };
    render(<AssistantCard card={card} spec={SPEC} />);
    expect(screen.getByLabelText(/Load check: Pass/)).toBeInTheDocument();
    expect(screen.queryByText("OK")).not.toBeInTheDocument();
  });

  it("shows Pass with warning when concentrated load fails (Bug 4)", () => {
    const frameData: FrameResponse = {
      ...FRAME_DATA_PASS,
      check_report: CONCENTRATED_FAIL_REPORT,
    };
    const card: AssistantCardType = {
      type: "edit",
      spec: SPEC,
      changes: [],
      frameData,
    };
    render(<AssistantCard card={card} spec={SPEC} />);
    // Must say "Pass with warning", NOT "OK"
    expect(screen.getByLabelText(/Load check: Pass with warning/)).toBeInTheDocument();
    expect(screen.queryByText("OK")).not.toBeInTheDocument();
  });

  it("shows Fail badge when load check fails", () => {
    const frameData: FrameResponse = {
      ...FRAME_DATA_PASS,
      check_report: FAILING_REPORT,
    };
    const card: AssistantCardType = {
      type: "edit",
      spec: SPEC,
      changes: [],
      frameData,
    };
    render(<AssistantCard card={card} spec={SPEC} />);
    expect(screen.getByLabelText(/Load check: Fail/)).toBeInTheDocument();
    expect(screen.queryByText("OK")).not.toBeInTheDocument();
  });
});

describe("AssistantCard next-step chips", () => {
  it("shows common chips when load passes", () => {
    const onChip = vi.fn();
    const card: AssistantCardType = {
      type: "edit",
      spec: SPEC,
      changes: [],
      frameData: FRAME_DATA_PASS,
    };
    render(<AssistantCard card={card} spec={SPEC} onChip={onChip} />);
    const chips = screen.getAllByTestId("next-step-chip");
    expect(chips.length).toBeGreaterThanOrEqual(1);
    expect(chips.length).toBeLessThanOrEqual(3);
  });

  it("calls onChip with chip text when clicked", () => {
    const onChip = vi.fn();
    const card: AssistantCardType = {
      type: "edit",
      spec: SPEC,
      changes: [],
      frameData: FRAME_DATA_PASS,
    };
    render(<AssistantCard card={card} spec={SPEC} onChip={onChip} />);
    fireEvent.click(screen.getAllByTestId("next-step-chip")[0]);
    expect(onChip).toHaveBeenCalledOnce();
    expect(typeof onChip.mock.calls[0][0]).toBe("string");
  });

  it("shows no chips when onChip is not provided", () => {
    const card: AssistantCardType = {
      type: "edit",
      spec: SPEC,
      changes: [],
      frameData: FRAME_DATA_PASS,
    };
    render(<AssistantCard card={card} spec={SPEC} />);
    expect(screen.queryAllByTestId("next-step-chip")).toHaveLength(0);
  });
});

describe("AssistantCard example (first-visit auto-load)", () => {
  it("shows the example message", () => {
    const card: AssistantCardType = {
      type: "example",
      spec: SPEC,
      message: "Here is an example to start from: workbench 1500 × 700 × 900 mm, 100 kg",
      frameData: null,
    };
    render(<AssistantCard card={card} spec={SPEC} />);
    expect(
      screen.getByText(
        "Here is an example to start from: workbench 1500 × 700 × 900 mm, 100 kg"
      )
    ).toBeInTheDocument();
  });

  it("shows StatusBadge when frameData is provided", () => {
    const card: AssistantCardType = {
      type: "example",
      spec: SPEC,
      message: "Here is an example to start from: workbench 1500 × 700 × 900 mm, 100 kg",
      frameData: FRAME_DATA_PASS,
    };
    render(<AssistantCard card={card} spec={SPEC} />);
    expect(screen.getByLabelText(/Load check:/)).toBeInTheDocument();
  });

  it("shows next-step chips when frameData and onChip provided", () => {
    const onChip = vi.fn();
    const card: AssistantCardType = {
      type: "example",
      spec: SPEC,
      message: "Here is an example to start from: workbench 1500 × 700 × 900 mm, 100 kg",
      frameData: FRAME_DATA_PASS,
    };
    render(<AssistantCard card={card} spec={SPEC} onChip={onChip} />);
    expect(screen.getAllByTestId("next-step-chip").length).toBeGreaterThanOrEqual(1);
  });
});

describe("AssistantCard error", () => {
  it("renders the error message", () => {
    const card: AssistantCardType = {
      type: "error",
      message: "Network error — please try again.",
    };
    render(<AssistantCard card={card} spec={null} />);
    expect(
      screen.getByText("Network error — please try again.")
    ).toBeInTheDocument();
  });
});
