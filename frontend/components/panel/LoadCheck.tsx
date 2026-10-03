import type { CheckReport } from "@/lib/types";
import { StatusBadge } from "@/components/StatusBadge";

interface LoadCheckProps {
  checkReport: CheckReport;
}

function fmt(n: number, digits = 2) {
  return n.toFixed(digits);
}

export function LoadCheck({ checkReport }: LoadCheckProps) {
  const { load, collision, connectivity } = checkReport;
  const gov = load.governing_rail;

  return (
    <div className="flex flex-col gap-3">
      <StatusBadge checkReport={checkReport} />

      {load.status === "not_evaluated" && load.not_evaluated_reason && (
        <p className="text-xs text-muted">{load.not_evaluated_reason}</p>
      )}

      {gov && (
        <div className="rounded border border-border bg-bg p-3 text-xs font-mono space-y-1">
          <p className="text-muted mb-1">Governing rail</p>
          <Row label="Span" value={`${gov.span_mm.toLocaleString()} mm`} />
          <Row
            label="Stress (dist / conc)"
            value={`${fmt(gov.distributed.bending_stress_mpa)} / ${fmt(gov.concentrated.bending_stress_mpa)} MPa`}
          />
          <Row
            label="Allow. stress"
            value={`${fmt(gov.allowable_stress_mpa)} MPa`}
          />
          <Row
            label="Deflection (dist / conc)"
            value={`${fmt(gov.distributed.deflection_mm)} / ${fmt(gov.concentrated.deflection_mm)} mm`}
          />
          <Row
            label="Allow. deflection"
            value={`${fmt(gov.deflection_limit_mm)} mm`}
          />
          <Row
            label="Utilisation"
            value={`${fmt(gov.utilisation * 100, 1)} %`}
          />
        </div>
      )}

      <p className="text-xs text-muted">
        These are estimates with a {load.safety_factor}× safety factor.
        Verify before building.
      </p>

      {!collision.passed && (
        <p className="text-xs text-fail">
          ✕ Collision: {collision.colliding_pairs.length} overlapping pair
          {collision.colliding_pairs.length !== 1 ? "s" : ""}
        </p>
      )}
      {!connectivity.passed && (
        <p className="text-xs text-fail">
          ✕ Connectivity: {connectivity.disconnected_bar_indices.length} disconnected bar
          {connectivity.disconnected_bar_indices.length !== 1 ? "s" : ""}
        </p>
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-2">
      <span className="text-muted">{label}</span>
      <span className="text-text">{value}</span>
    </div>
  );
}
