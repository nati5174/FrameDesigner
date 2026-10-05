import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CutList } from "@/components/panel/CutList";
import type { CutListRow } from "@/lib/types";

const ROWS: CutListRow[] = [
  { profile_id: "HPS8-2020", length_mm: 900, qty: 4, total_mm: 3600, cost_usd: null, weight_kg: null },
  { profile_id: "HPS8-2020", length_mm: 1420, qty: 2, total_mm: 2840, cost_usd: null, weight_kg: null },
  { profile_id: "HPS8-2020", length_mm: 620, qty: 2, total_mm: 1240, cost_usd: null, weight_kg: null },
];

describe("CutList", () => {
  it("renders all rows", () => {
    render(<CutList rows={ROWS} />);
    expect(screen.getAllByText(/HPS8-2020/).length).toBe(3);
  });

  it("shows the grand total", () => {
    render(<CutList rows={ROWS} />);
    // 3600 + 2840 + 1240 = 7680
    expect(screen.getByText(/7,680/)).toBeInTheDocument();
  });

  it("renders qty with × prefix", () => {
    render(<CutList rows={ROWS} />);
    expect(screen.getByText("×4")).toBeInTheDocument();
  });

  it("renders empty table without crashing", () => {
    render(<CutList rows={[]} />);
    expect(screen.getByText(/Total bar length/)).toBeInTheDocument();
  });

  it("shows n/a and no-price disclaimer when totalCostUsd is null", () => {
    render(<CutList rows={ROWS} totalCostUsd={null} />);
    expect(screen.getByText("n/a")).toBeInTheDocument();
    expect(screen.getByText(/no price data for this profile/)).toBeInTheDocument();
  });

  it("shows cost and disclaimer when totalCostUsd is provided", () => {
    render(<CutList rows={ROWS} totalCostUsd={42.5} />);
    expect(screen.getByText("$42.50")).toBeInTheDocument();
    expect(screen.getByText(/See Parts list/)).toBeInTheDocument();
    expect(screen.queryByText(/no price data/)).not.toBeInTheDocument();
  });
});
