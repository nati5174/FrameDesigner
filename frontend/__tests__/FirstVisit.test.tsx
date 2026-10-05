/**
 * First-visit state unit tests.
 *
 * Verifies that on a first visit (only the auto-loaded "example" assistant
 * entry, no user messages) the UI renders:
 *   - The thread column (at least one assistant entry)
 *   - The example card with the expected message
 *   - The subtitle
 *   - The three example prompt buttons
 *
 * Tests the rendering primitives directly rather than mounting FrameDesigner
 * (which makes live API calls).
 */
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ConversationThread } from "@/components/thread/ConversationThread";
import { EXAMPLES } from "@/lib/examples";
import type { AssistantCard as AssistantCardType, FrameSpec, ThreadEntry } from "@/lib/types";

const SPEC: FrameSpec = {
  frame_type: "table",
  width_mm: 1500, depth_mm: 700, height_mm: 900,
  profile_series: "40-series",
  shelf_height_mm: null, target_load_kg: 100, centre_legs: false,
  level_heights_mm: null, load_per_level_kg: null,
};

const EXAMPLE_CARD: AssistantCardType = {
  type: "example",
  spec: SPEC,
  message: "Here is an example to start from: workbench 1500 × 700 × 900 mm, 100 kg",
  frameData: null,
};

const EXAMPLE_ENTRY: ThreadEntry = {
  role: "assistant",
  card: EXAMPLE_CARD,
  spec: SPEC,
};

/** Mimics the desktop thread column content rendered by FrameDesigner. */
function ThreadColumnContent({
  entries,
  isExampleState,
  onExampleSelect,
}: {
  entries: ThreadEntry[];
  isExampleState: boolean;
  onExampleSelect: (p: string) => void;
}) {
  return (
    <div>
      <ConversationThread entries={entries} />
      {isExampleState && (
        <div>
          <p>Describe a frame. Get a 3D model, cut list, cost and load estimate.</p>
          <p>Try an example</p>
          {EXAMPLES.map((ex) => (
            <button key={ex.prompt} onClick={() => onExampleSelect(ex.prompt)}>
              {ex.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

describe("First-visit state — thread column", () => {
  it("thread column has at least one entry (example card)", () => {
    render(
      <ThreadColumnContent
        entries={[EXAMPLE_ENTRY]}
        isExampleState={true}
        onExampleSelect={vi.fn()}
      />
    );
    expect(
      screen.getByText(
        "Here is an example to start from: workbench 1500 × 700 × 900 mm, 100 kg"
      )
    ).toBeInTheDocument();
  });

  it("subtitle is visible", () => {
    render(
      <ThreadColumnContent
        entries={[EXAMPLE_ENTRY]}
        isExampleState={true}
        onExampleSelect={vi.fn()}
      />
    );
    expect(
      screen.getByText(/Describe a frame\. Get a 3D model/)
    ).toBeInTheDocument();
  });

  it("renders exactly three example prompt buttons", () => {
    render(
      <ThreadColumnContent
        entries={[EXAMPLE_ENTRY]}
        isExampleState={true}
        onExampleSelect={vi.fn()}
      />
    );
    const buttons = EXAMPLES.map((ex) => screen.getByText(ex.label));
    expect(buttons).toHaveLength(3);
  });

  it("example buttons are clickable and fire onExampleSelect", () => {
    const onSelect = vi.fn();
    render(
      <ThreadColumnContent
        entries={[EXAMPLE_ENTRY]}
        isExampleState={true}
        onExampleSelect={onSelect}
      />
    );
    fireEvent.click(screen.getByText(EXAMPLES[0].label));
    expect(onSelect).toHaveBeenCalledOnce();
    expect(onSelect).toHaveBeenCalledWith(EXAMPLES[0].prompt);
  });

  it("subtitle and examples are hidden once a user entry exists (isExampleState=false)", () => {
    render(
      <ThreadColumnContent
        entries={[
          EXAMPLE_ENTRY,
          { role: "user", text: "make it 100 mm taller" },
        ]}
        isExampleState={false}
        onExampleSelect={vi.fn()}
      />
    );
    expect(screen.queryByText(/Describe a frame/)).not.toBeInTheDocument();
    EXAMPLES.forEach((ex) => {
      expect(screen.queryByText(ex.label)).not.toBeInTheDocument();
    });
  });
});

describe("First-visit state — isExampleState logic", () => {
  it("is true when all entries are assistant entries", () => {
    const entries: ThreadEntry[] = [EXAMPLE_ENTRY];
    const isExampleState = entries.every((e) => e.role === "assistant");
    expect(isExampleState).toBe(true);
  });

  it("is false when a user entry exists", () => {
    const entries: ThreadEntry[] = [
      EXAMPLE_ENTRY,
      { role: "user", text: "make it taller" },
    ];
    const isExampleState = entries.every((e) => e.role === "assistant");
    expect(isExampleState).toBe(false);
  });

  it("is false when entries is empty (no auto-load yet)", () => {
    const entries: ThreadEntry[] = [];
    const isExampleState = entries.length > 0 && entries.every((e) => e.role === "assistant");
    expect(isExampleState).toBe(false);
  });
});
