import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StatusBadge } from "@/components/StatusBadge";
import type { CheckReport, RailCheck } from "@/lib/types";

function makeRailCheck(overrides: Partial<RailCheck> = {}): RailCheck {
  return {
    bar_index: 0,
    role: "top_rail_width",
    span_mm: 1500,
    allowable_stress_mpa: 57.46,
    deflection_limit_mm: 4.8,
    utilisation: 0.5,
    distributed: {
      moment_n_mm: 1000,
      bending_stress_mpa: 10,
      deflection_mm: 1,
      stress_passed: true,
      deflection_passed: true,
      passed: true,
    },
    concentrated: {
      moment_n_mm: 800,
      bending_stress_mpa: 8,
      deflection_mm: 0.8,
      stress_passed: true,
      deflection_passed: true,
      passed: true,
    },
    passed: true,
    ...overrides,
  };
}

function makeReport(
  passed: boolean,
  governingRail: RailCheck | null = null
): CheckReport {
  return {
    collision: { passed: true, colliding_pairs: [] },
    connectivity: { passed: true, disconnected_bar_indices: [] },
    load: {
      is_estimate: true,
      safety_factor: 3,
      deflection_limit_fraction: 500,
      status: "evaluated",
      not_evaluated_reason: null,
      governing_rail: governingRail,
      all_rails: governingRail ? [governingRail] : [],
      passed,
    },
    passed,
    leg_check: null,
    tipping: null,
  };
}

describe("StatusBadge", () => {
  it("shows Pass when check_report.passed is true and concentrated passes", () => {
    const rail = makeRailCheck();
    render(<StatusBadge checkReport={makeReport(true, rail)} />);
    expect(screen.getByText("Pass")).toBeInTheDocument();
  });

  it("shows Fail when check_report.passed is false", () => {
    render(<StatusBadge checkReport={makeReport(false)} />);
    expect(screen.getByText("Fail")).toBeInTheDocument();
  });

  it("shows Pass with warning when distributed passes but concentrated fails", () => {
    const rail = makeRailCheck({
      concentrated: {
        moment_n_mm: 9999,
        bending_stress_mpa: 99,
        deflection_mm: 99,
        stress_passed: false,
        deflection_passed: false,
        passed: false,
      },
    });
    render(<StatusBadge checkReport={makeReport(true, rail)} />);
    expect(screen.getByText("Pass with warning")).toBeInTheDocument();
  });

  it("has an accessible aria-label", () => {
    render(<StatusBadge checkReport={makeReport(true)} />);
    expect(screen.getByRole("generic", { name: /Load check:/i })).toBeInTheDocument();
  });
});
