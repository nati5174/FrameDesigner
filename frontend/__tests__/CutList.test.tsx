import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CutList } from "@/components/panel/CutList";
import type { CutListRow } from "@/lib/types";

const ROWS: CutListRow[] = [
  { profile_id: "HPS8-2020", length_mm: 900, qty: 4, total_mm: 3600 },
  { profile_id: "HPS8-2020", length_mm: 1420, qty: 2, total_mm: 2840 },
  { profile_id: "HPS8-2020", length_mm: 620, qty: 2, total_mm: 1240 },
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
});
