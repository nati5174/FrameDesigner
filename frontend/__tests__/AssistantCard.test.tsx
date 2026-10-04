import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AssistantCard } from "@/components/thread/AssistantCard";
import type { AssistantCard as AssistantCardType, FrameSpec } from "@/lib/types";

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

  it("shows defaults applied", () => {
    const card: AssistantCardType = {
      type: "new_design",
      spec: SPEC,
      changes: [],
      defaults: ["height_mm=900"],
      frameData: null,
    };
    render(<AssistantCard card={card} spec={SPEC} />);
    expect(screen.getByText(/Defaults applied/)).toBeInTheDocument();
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

  it("shows changed fields", () => {
    const card: AssistantCardType = {
      type: "edit",
      spec: SPEC,
      changes: [{ field: "height_mm", old: 900, new: 1100 }],
      frameData: null,
    };
    render(<AssistantCard card={card} spec={SPEC} />);
    expect(screen.getByText(/height changed/)).toBeInTheDocument();
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
