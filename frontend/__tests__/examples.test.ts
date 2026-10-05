import { describe, expect, it } from "vitest";
import { EXAMPLES, DEFAULT_SPEC } from "@/lib/examples";

describe("EXAMPLES", () => {
  it("has exactly three examples", () => {
    expect(EXAMPLES.length).toBe(3);
  });

  it("every example has a non-empty prompt and label", () => {
    for (const ex of EXAMPLES) {
      expect(ex.prompt.trim().length).toBeGreaterThan(0);
      expect(ex.label.trim().length).toBeGreaterThan(0);
    }
  });

  it("no two examples share the same prompt", () => {
    const prompts = EXAMPLES.map((e) => e.prompt);
    const unique = new Set(prompts);
    expect(unique.size).toBe(prompts.length);
  });

  it("all prompts are under 500 characters (API limit)", () => {
    for (const ex of EXAMPLES) {
      expect(ex.prompt.length).toBeLessThanOrEqual(500);
    }
  });

  it("first example is the workbench prompt", () => {
    expect(EXAMPLES[0].prompt).toBe("workbench 1500 x 700 mm, holds 100 kg");
  });

  it("second example is the wide bench prompt", () => {
    expect(EXAMPLES[1].prompt).toBe("bench 3000 x 700 x 900 mm, holds 100 kg");
  });

  it("third example is the shelf unit prompt", () => {
    expect(EXAMPLES[2].prompt).toBe("shelf unit 900 x 400 x 1800, 4 levels, 30 kg per level");
  });
});

describe("DEFAULT_SPEC", () => {
  it("is a 1500 × 700 × 900 mm table at 100 kg", () => {
    expect(DEFAULT_SPEC.frame_type).toBe("table");
    expect(DEFAULT_SPEC.width_mm).toBe(1500);
    expect(DEFAULT_SPEC.depth_mm).toBe(700);
    expect(DEFAULT_SPEC.height_mm).toBe(900);
    expect(DEFAULT_SPEC.target_load_kg).toBe(100);
  });

  it("uses 40-series profile by default", () => {
    expect(DEFAULT_SPEC.profile_series).toBe("40-series");
  });

  it("has no centre legs and no shelf", () => {
    expect(DEFAULT_SPEC.centre_legs).toBe(false);
    expect(DEFAULT_SPEC.shelf_height_mm).toBeNull();
    expect(DEFAULT_SPEC.level_heights_mm).toBeNull();
    expect(DEFAULT_SPEC.load_per_level_kg).toBeNull();
  });
});
