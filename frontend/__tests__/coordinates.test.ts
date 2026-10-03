import { describe, expect, it } from "vitest";
import { toThree } from "@/lib/coordinates";

describe("toThree", () => {
  it("maps origin to origin", () => {
    const [tx, ty, tz] = toThree(0, 0, 0);
    expect(tx).toBe(0);
    expect(ty).toBe(0);
    // -0 and +0 are numerically equal; both are correct here
    expect(Math.abs(tz)).toBe(0);
  });

  it("+X stays +X (width axis unchanged)", () => {
    const [tx, ty, tz] = toThree(100, 0, 0);
    expect(tx).toBe(100);
    expect(ty).toBe(0);
    expect(Math.abs(tz)).toBe(0);
  });

  it("+Z (up) maps to +Y in Three.js", () => {
    const [tx, ty, tz] = toThree(0, 0, 900);
    expect(Math.abs(tx)).toBe(0);
    expect(ty).toBe(900);
    expect(Math.abs(tz)).toBe(0);
  });

  it("+Y (depth) maps to -Z in Three.js (right-hand)", () => {
    const [tx, ty, tz] = toThree(0, 700, 0);
    expect(tx).toBe(0);
    expect(ty).toBe(0);
    expect(tz).toBe(-700);
  });

  it("handles a typical bar endpoint", () => {
    // Frame point (1500, 700, 900) → Three.js (1500, 900, -700)
    expect(toThree(1500, 700, 900)).toEqual([1500, 900, -700]);
  });
});
