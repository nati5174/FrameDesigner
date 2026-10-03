import { describe, expect, it } from "vitest";
import { EXAMPLES } from "@/lib/examples";

describe("EXAMPLES", () => {
  it("has at least one example", () => {
    expect(EXAMPLES.length).toBeGreaterThan(0);
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
});
