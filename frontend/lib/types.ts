// All types mirror the FastAPI response shapes exactly.
// The frontend never computes pass/fail or lengths — it only displays what the API returns.

export interface FrameSpec {
  frame_type: "table" | "shelf_unit";
  width_mm: number;
  depth_mm: number;
  height_mm: number;
  profile_series: string;
  // table fields
  shelf_height_mm: number | null;
  target_load_kg: number | null;
  centre_legs: boolean;
  // shelf unit fields
  level_heights_mm: number[] | null;
  load_per_level_kg: number | null;
}

// /parse ─────────────────────────────────────────────────────────────────────

export interface ParseResponse {
  outcome: "spec_valid" | "spec_invalid" | "not_parsed";
  spec: FrameSpec | null;
  error: string | null;
  defaults_applied: string[];
  parser_used: "rule_based" | "llm" | "none";
  llm_available: boolean;
}

// /frame ─────────────────────────────────────────────────────────────────────

export interface BarData {
  start: [number, number, number];
  end: [number, number, number];
  profile_width_mm: number;
  role: string;
}

export interface CutListRow {
  profile_id: string;
  length_mm: number;
  qty: number;
  total_mm: number;
}

export interface RailLoadCase {
  moment_n_mm: number;
  bending_stress_mpa: number;
  deflection_mm: number;
  stress_passed: boolean;
  deflection_passed: boolean;
  passed: boolean;
}

export interface RailCheck {
  bar_index: number;
  role: string;
  span_mm: number;
  allowable_stress_mpa: number;
  deflection_limit_mm: number;
  utilisation: number;
  distributed: RailLoadCase;
  concentrated: RailLoadCase;
  passed: boolean;
}

export interface LoadEstimate {
  is_estimate: boolean;
  safety_factor: number;
  deflection_limit_fraction: number;
  status: "evaluated" | "not_evaluated";
  not_evaluated_reason: string | null;
  governing_rail: RailCheck | null;
  all_rails: RailCheck[];
  passed: boolean;
}

export interface LegCheck {
  is_estimate: boolean;
  safety_factor: number;
  f_total_n: number;
  f_leg_n: number;
  k_factor: number;
  effective_length_mm: number;
  buckling_status: "evaluated" | "not_evaluated";
  buckling_not_evaluated_reason: string | null;
  p_cr_n: number | null;
  p_cr_allowable_n: number | null;
  buckling_passed: boolean;
  compressive_stress_status: "evaluated" | "not_evaluated";
  compressive_stress_reason: string | null;
  compressive_stress_mpa: number | null;
  compressive_stress_allowable_mpa: number | null;
  compressive_stress_passed: boolean | null;
  passed: boolean;
}

export interface TippingCheck {
  h_to_d_ratio: number;
  threshold: number;
  warning: boolean;
  message: string | null;
}

export interface CollisionCheck {
  passed: boolean;
  colliding_pairs: [number, number][];
}

export interface ConnectivityCheck {
  passed: boolean;
  disconnected_bar_indices: number[];
}

export interface CheckReport {
  collision: CollisionCheck;
  connectivity: ConnectivityCheck;
  load: LoadEstimate;
  passed: boolean;
  leg_check: LegCheck | null;
  tipping: TippingCheck | null;
  not_covered: string[];
}

export interface FixCandidate {
  fix_type:
    | "reduce_span_width"
    | "reduce_span_depth"
    | "reduce_load"
    | "centre_legs"
    | "reduce_load_per_level";
  spec: FrameSpec;
  check_report: CheckReport;
  trade_off: string;
  resolves: "distributed" | "concentrated";
  concentrated_warning_remains: boolean;
}

export interface FrameResponse {
  bars: BarData[];
  cut_list: CutListRow[];
  check_report: CheckReport;
  suggestions: FixCandidate[];
}
