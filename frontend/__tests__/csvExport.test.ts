import { describe, expect, it } from "vitest";
import { buildCutListCsv, buildPartsListCsv, csvEscape } from "@/lib/csvExport";
import type { CutListRow, FrameSpec, PartsListRow } from "@/lib/types";

// ─── Reference data: 1500 × 700 × 900 table, 40-series ───────────────────────
// Bars: 4 × 900 mm legs, 2 × 1420 mm long rails, 2 × 620 mm short rails
// price_per_mm = 0.0441, cut_charge = $3.00/cut
// Total bars+cuts ≈ $362.69 (exact float sum from backend)

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

const CUT_LIST_ROWS: CutListRow[] = [
  { profile_id: "40-4040", length_mm: 620, qty: 2, total_mm: 1240, cost_usd: 60.684, weight_kg: 2.925 },
  { profile_id: "40-4040", length_mm: 900, qty: 4, total_mm: 3600, cost_usd: 170.76, weight_kg: 8.492 },
  { profile_id: "40-4040", length_mm: 1420, qty: 2, total_mm: 2840, cost_usd: 131.244, weight_kg: 6.699 },
];

const PARTS_LIST_ROWS: PartsListRow[] = [
  {
    part_number: "40-4302",
    description: "40 Series 2 Hole Inside Corner Bracket, Al 6063-T6, clear anodize, 40x40 mm",
    qty: 8,
    unit_price_usd: 5.31,
    line_total_usd: 42.48,
    source_url: "https://8020.net/40-4302.html",
  },
  {
    part_number: "13-8316",
    description: "M8x16mm Button Head Socket Cap Screw (BHSCS), steel, zinc",
    qty: 16,
    unit_price_usd: 0.61,
    line_total_usd: 9.76,
    source_url: "https://8020.net/13-8316.html",
  },
  {
    part_number: "3838",
    description: "M8 Slide-In Economy T-Nut, offset thread, steel, bright zinc",
    qty: 16,
    unit_price_usd: 0.53,
    line_total_usd: 8.48,
    source_url: "https://8020.net/3838.html",
  },
];

const FIXED_TODAY = "2026-10-05";

// ─── csvEscape ────────────────────────────────────────────────────────────────

describe("csvEscape", () => {
  it("returns empty string for null", () => {
    expect(csvEscape(null)).toBe("");
  });

  it("returns empty string for undefined", () => {
    expect(csvEscape(undefined)).toBe("");
  });

  it("leaves plain text unchanged", () => {
    expect(csvEscape("hello world")).toBe("hello world");
  });

  it("wraps field containing comma in double quotes", () => {
    expect(csvEscape("a, b")).toBe('"a, b"');
  });

  it("escapes embedded double quotes as two double quotes", () => {
    expect(csvEscape('say "hi"')).toBe('"say ""hi"""');
  });

  it("wraps field containing newline in double quotes", () => {
    expect(csvEscape("line1\nline2")).toBe('"line1\nline2"');
  });

  it("converts numbers to strings", () => {
    expect(csvEscape(42.5)).toBe("42.5");
  });
});

// ─── buildCutListCsv ──────────────────────────────────────────────────────────

describe("buildCutListCsv — 1500×700×900 table", () => {
  const { content, filename } = buildCutListCsv(
    SPEC,
    CUT_LIST_ROWS,
    362.69,
    "v4",
    FIXED_TODAY,
  );

  it("filename is correct", () => {
    expect(filename).toBe("frame-cut-list-1500x700x900.csv");
  });

  it("contains design summary header", () => {
    expect(content).toContain("# Design: table, 1500 x 700 x 900 mm, load 100 kg, 40-series");
  });

  it("contains date header", () => {
    expect(content).toContain("# Date: 2026-10-05");
  });

  it("contains catalog version header", () => {
    expect(content).toContain("# Catalog: v4");
  });

  it("contains disclaimer", () => {
    expect(content).toContain("Load results are estimates, not certified engineering.");
  });

  it("contains column header row", () => {
    expect(content).toContain("profile_id,length_mm,qty,unit_cost_usd,line_cost_usd");
  });

  it("has exactly 3 bar data rows", () => {
    const dataLines = content
      .split("\n")
      .filter((l) => l.startsWith("40-4040"));
    expect(dataLines).toHaveLength(3);
  });

  it("contains total bars+cuts", () => {
    expect(content).toContain("362.69");
  });

  it("shows line cost for 900mm bars", () => {
    // 170.76 is the line cost for 4 × 900mm
    expect(content).toContain("170.76");
  });

  it("shows unit cost for 900mm bars", () => {
    // unit = 170.76 / 4 = 42.69
    expect(content).toContain("42.69");
  });
});

describe("buildCutListCsv — no cost data", () => {
  it("shows n/a total when totalCostUsd is null", () => {
    const rowsNoCost: CutListRow[] = [
      { profile_id: "20-2020", length_mm: 500, qty: 2, total_mm: 1000, cost_usd: null, weight_kg: null },
    ];
    const { content } = buildCutListCsv(SPEC, rowsNoCost, null, "v4", FIXED_TODAY);
    expect(content).toContain("n/a");
  });
});

// ─── buildPartsListCsv ────────────────────────────────────────────────────────

describe("buildPartsListCsv — 1500×700×900 table, hardware priced", () => {
  const { content, filename } = buildPartsListCsv(
    SPEC,
    CUT_LIST_ROWS,
    PARTS_LIST_ROWS,
    362.69,
    60.72,
    423.41,
    true,
    "v4",
    FIXED_TODAY,
  );

  it("filename is correct", () => {
    expect(filename).toBe("frame-parts-list-1500x700x900.csv");
  });

  it("contains design summary header", () => {
    expect(content).toContain("# Design: table, 1500 x 700 x 900 mm, load 100 kg, 40-series");
  });

  it("contains column header row", () => {
    expect(content).toContain(
      "part_number,description,qty,unit_price_usd,line_total_usd,source_url",
    );
  });

  it("has 3 bar rows", () => {
    const barLines = content.split("\n").filter((l) => l.startsWith("40-4040,bar "));
    expect(barLines).toHaveLength(3);
  });

  it("has 3 hardware rows", () => {
    const hwLines = content.split("\n").filter((l) => /^(40-4302|13-8316|3838),/.test(l));
    expect(hwLines).toHaveLength(3);
  });

  it("shows bars + cuts subtotal $362.69", () => {
    expect(content).toContain("362.69");
  });

  it("shows hardware subtotal $60.72", () => {
    expect(content).toContain("60.72");
  });

  it("shows grand total $423.41", () => {
    expect(content).toContain("423.41");
  });

  it("includes source URL for bracket", () => {
    expect(content).toContain("https://8020.net/40-4302.html");
  });

  it("does NOT include 'hardware not priced' note", () => {
    expect(content).not.toContain("hardware not priced");
  });
});

describe("buildPartsListCsv — hardware not priced", () => {
  const { content, filename } = buildPartsListCsv(
    SPEC,
    CUT_LIST_ROWS,
    [],
    362.69,
    null,
    null,
    false,
    "v4",
    FIXED_TODAY,
  );

  it("filename is correct", () => {
    expect(filename).toBe("frame-parts-list-1500x700x900.csv");
  });

  it("contains 'bars and cuts only, hardware not priced' note", () => {
    expect(content).toContain("bars and cuts only, hardware not priced");
  });

  it("has 3 bar rows", () => {
    const barLines = content.split("\n").filter((l) => l.startsWith("40-4040,bar "));
    expect(barLines).toHaveLength(3);
  });

  it("has no hardware rows", () => {
    const hwLines = content.split("\n").filter((l) => /^(40-4302|13-8316|3838),/.test(l));
    expect(hwLines).toHaveLength(0);
  });

  it("shows bars subtotal", () => {
    expect(content).toContain("362.69");
  });

  it("does NOT show grand total line when null", () => {
    const totalLines = content.split("\n").filter((l) => l.startsWith(",Total,"));
    expect(totalLines).toHaveLength(0);
  });
});

describe("buildPartsListCsv — CSV escaping", () => {
  it("quotes a description that contains a comma", () => {
    const rowWithComma: PartsListRow = {
      part_number: "XY-001",
      description: "Bracket, heavy duty",
      qty: 1,
      unit_price_usd: 9.99,
      line_total_usd: 9.99,
      source_url: "https://example.com",
    };
    const { content } = buildPartsListCsv(
      SPEC,
      [],
      [rowWithComma],
      null,
      9.99,
      9.99,
      true,
      "v4",
      FIXED_TODAY,
    );
    expect(content).toContain('"Bracket, heavy duty"');
  });

  it("escapes a description that contains a double quote", () => {
    const rowWithQuote: PartsListRow = {
      part_number: "XY-002",
      description: '3" bracket',
      qty: 1,
      unit_price_usd: 5.00,
      line_total_usd: 5.00,
      source_url: "https://example.com",
    };
    const { content } = buildPartsListCsv(
      SPEC,
      [],
      [rowWithQuote],
      null,
      5.00,
      5.00,
      true,
      "v4",
      FIXED_TODAY,
    );
    expect(content).toContain('"3"" bracket"');
  });
});
