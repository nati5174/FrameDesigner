import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { LoadCheck } from "@/components/panel/LoadCheck";
import type { CheckReport, RailCheck } from "@/lib/types";

function makePassingReport(): CheckReport {
  return {
    collision: { passed: true, colliding_pairs: [] },
    connectivity: { passed: true, disconnected_bar_indices: [] },
    load: {
      is_estimate: true,
      safety_factor: 3,
      deflection_limit_fraction: 500,
      status: "evaluated",
      not_evaluated_reason: null,
      governing_rail: null,
      all_rails: [],
      passed: true,
    },
    passed: true,
    leg_check: null,
    tipping: null,
    not_covered: [],
  };
}

function makeGovRail(): RailCheck {
  return {
    bar_index: 0,
    role: "top_rail_width",
    span_mm: 1500,
    allowable_stress_mpa: 57.46,
    deflection_limit_mm: 3.0,
    utilisation: 0.22,
    distributed: {
      moment_n_mm: 50000,
      bending_stress_mpa: 12.81,
      deflection_mm: 2.01,
      stress_passed: true,
      deflection_passed: true,
      passed: true,
    },
    concentrated: {
      moment_n_mm: 30000,
      bending_stress_mpa: 8.0,
      deflection_mm: 1.5,
      stress_passed: true,
      deflection_passed: true,
      passed: true,
    },
    passed: true,
  };
}

describe("LoadCheck", () => {
  it("renders the StatusBadge", () => {
    render(<LoadCheck checkReport={makePassingReport()} />);
    expect(screen.getByRole("generic", { name: /Load check:/i })).toBeInTheDocument();
  });

  it("shows the estimate disclaimer", () => {
    render(<LoadCheck checkReport={makePassingReport()} />);
    expect(screen.getByText(/estimates with a 3× safety factor/i)).toBeInTheDocument();
  });

  it("renders governing rail stats when present", () => {
    const report = makePassingReport();
    const gov = makeGovRail();
    report.load.governing_rail = gov;
    report.load.all_rails = [gov];

    render(<LoadCheck checkReport={report} />);
    expect(screen.getByText(/1,500 mm/)).toBeInTheDocument();
    expect(screen.getByText(/57.46 MPa/)).toBeInTheDocument();
  });

  it("reports collision failures", () => {
    const report = makePassingReport();
    report.collision = { passed: false, colliding_pairs: [[0, 1]] };
    report.passed = false;

    render(<LoadCheck checkReport={report} />);
    expect(screen.getByText(/Collision: 1 overlapping pair/)).toBeInTheDocument();
  });

  it("reports connectivity failures", () => {
    const report = makePassingReport();
    report.connectivity = { passed: false, disconnected_bar_indices: [2, 3] };
    report.passed = false;

    render(<LoadCheck checkReport={report} />);
    expect(screen.getByText(/Connectivity: 2 disconnected bars/)).toBeInTheDocument();
  });
});
