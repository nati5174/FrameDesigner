import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useThread } from "@/hooks/useThread";
import type { FrameSpec } from "@/lib/types";

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

describe("useThread", () => {
  it("starts empty", () => {
    const { result } = renderHook(() => useThread());
    expect(result.current.entries).toHaveLength(0);
    expect(result.current.currentSpec).toBeNull();
    expect(result.current.pending).toBeNull();
  });

  it("addUserEntry appends a user entry", () => {
    const { result } = renderHook(() => useThread());
    act(() => result.current.addUserEntry("hello"));
    expect(result.current.entries).toHaveLength(1);
    expect(result.current.entries[0]).toMatchObject({ role: "user", text: "hello" });
  });

  it("addLoadingEntry appends a loading assistant entry", () => {
    const { result } = renderHook(() => useThread());
    act(() => result.current.addLoadingEntry());
    expect(result.current.entries).toHaveLength(1);
    const entry = result.current.entries[0];
    expect(entry.role).toBe("assistant");
    if (entry.role === "assistant") {
      expect(entry.card.type).toBe("loading");
    }
  });

  it("resolveLastEntry replaces loading entry with resolved card", () => {
    const { result } = renderHook(() => useThread());
    act(() => {
      result.current.addUserEntry("make it taller");
      result.current.addLoadingEntry();
    });
    act(() => {
      result.current.resolveLastEntry(
        { type: "edit", spec: SPEC, changes: [], frameData: null },
        SPEC,
        null
      );
    });
    expect(result.current.entries).toHaveLength(2);
    const last = result.current.entries[1];
    expect(last.role).toBe("assistant");
    if (last.role === "assistant") {
      expect(last.card.type).toBe("edit");
    }
    expect(result.current.currentSpec).toEqual(SPEC);
  });

  it("resolveLastEntry updates currentSpec when spec provided", () => {
    const { result } = renderHook(() => useThread());
    act(() => result.current.addLoadingEntry());
    act(() =>
      result.current.resolveLastEntry(
        { type: "edit", spec: SPEC, changes: [], frameData: null },
        SPEC,
        null
      )
    );
    expect(result.current.currentSpec).toEqual(SPEC);
  });

  it("resolveLastEntry does not update currentSpec when spec is null", () => {
    const { result } = renderHook(() => useThread());
    act(() => result.current.addLoadingEntry());
    act(() =>
      result.current.resolveLastEntry(
        { type: "clarify", pending: {}, missing: ["depth_mm"] },
        null,
        {}
      )
    );
    expect(result.current.currentSpec).toBeNull();
    expect(result.current.pending).toEqual({});
  });

  it("restoreToSpec sets currentSpec and clears pending", () => {
    const { result } = renderHook(() => useThread());
    act(() => result.current.resolveLastEntry(
      { type: "clarify", pending: {}, missing: [] },
      null,
      { width_mm: 1500 }
    ));
    // pending is now set; restore overrides
    act(() => result.current.addLoadingEntry());
    act(() => result.current.restoreToSpec(SPEC));
    expect(result.current.currentSpec).toEqual(SPEC);
    expect(result.current.pending).toBeNull();
  });

  it("clear resets all state", () => {
    const { result } = renderHook(() => useThread());
    act(() => {
      result.current.addUserEntry("hello");
      result.current.addLoadingEntry();
    });
    act(() => result.current.clear());
    expect(result.current.entries).toHaveLength(0);
    expect(result.current.currentSpec).toBeNull();
  });
});
