import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PartsList } from "@/components/panel/PartsList";
import type { PartsListRow } from "@/lib/types";

// Test A values: 1500×700×900 table, 40-series, 8 joints
const ROWS_A: PartsListRow[] = [
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

describe("PartsList — hardware priced", () => {
  it("renders all part rows", () => {
    render(
      <PartsList
        rows={ROWS_A}
        hardwareCostUsd={60.72}
        hardwareWeightKg={0.595}
        barsCostUsd={362.69}
        barsWeightKg={18.12}
        totalCostUsd={423.41}
        totalWeightKg={18.715}
        hardwarePriced={true}
      />
    );
    expect(screen.getByText("40-4302")).toBeInTheDocument();
    expect(screen.getByText("13-8316")).toBeInTheDocument();
    expect(screen.getByText("3838")).toBeInTheDocument();
  });

  it("shows correct hardware total", () => {
    render(
      <PartsList
        rows={ROWS_A}
        hardwareCostUsd={60.72}
        hardwareWeightKg={0.595}
        barsCostUsd={362.69}
        barsWeightKg={18.12}
        totalCostUsd={423.41}
        totalWeightKg={18.715}
        hardwarePriced={true}
      />
    );
    // $60.72 appears in tfoot (hardware total) and in breakdown row
    expect(screen.getAllByText("$60.72").length).toBeGreaterThanOrEqual(1);
  });

  it("shows cost breakdown with bars, hardware, and total", () => {
    render(
      <PartsList
        rows={ROWS_A}
        hardwareCostUsd={60.72}
        hardwareWeightKg={0.595}
        barsCostUsd={362.69}
        barsWeightKg={18.12}
        totalCostUsd={423.41}
        totalWeightKg={18.715}
        hardwarePriced={true}
      />
    );
    expect(screen.getByText("$362.69")).toBeInTheDocument();
    expect(screen.getByText("$423.41")).toBeInTheDocument();
  });

  it("links part numbers to vendor pages", () => {
    render(
      <PartsList
        rows={ROWS_A}
        hardwareCostUsd={60.72}
        hardwareWeightKg={null}
        barsCostUsd={362.69}
        barsWeightKg={18.12}
        totalCostUsd={423.41}
        totalWeightKg={null}
        hardwarePriced={true}
      />
    );
    const link = screen.getByRole("link", { name: "40-4302" });
    expect(link).toHaveAttribute("href", "https://8020.net/40-4302.html");
  });
});

describe("PartsList — hardware not priced", () => {
  it("shows not-available message when hardware_priced is false", () => {
    render(
      <PartsList
        rows={[]}
        hardwareCostUsd={null}
        hardwareWeightKg={null}
        barsCostUsd={200}
        barsWeightKg={10}
        totalCostUsd={null}
        totalWeightKg={null}
        hardwarePriced={false}
      />
    );
    expect(screen.getByText(/Hardware pricing not available/)).toBeInTheDocument();
  });
});
