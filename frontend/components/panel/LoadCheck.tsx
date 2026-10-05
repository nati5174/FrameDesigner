import type { CheckReport, LegCheck, RailCheck } from "@/lib/types";
import { formatRole } from "@/lib/labels";

interface LoadCheckProps {
  checkReport: CheckReport;
}

function fmt(n: number, digits = 2) {
  return n.toFixed(digits);
}

function Row({ label, value, fail }: { label: string; value: string; fail?: boolean }) {
  return (
    <div className="flex justify-between gap-2">
      <span className="text-muted">{label}</span>
      <span className={fail ? "text-fail" : "text-text"}>{value}</span>
    </div>
  );
}

function RailCard({ rail, governing }: { rail: RailCheck; governing: boolean }) {
  return (
    <div
      className={`rounded border p-3 text-xs font-mono space-y-1 ${
        governing
          ? "border-rule bg-surface"
          : "border-border bg-bg"
      }`}
    >
      <p className="text-muted mb-1">
        {governing ? "★ Governing rail" : "Rail"}
        {" "}
        <span className="text-text">{formatRole(rail.role)}</span>
      </p>
      <Row label="Span" value={`${rail.span_mm.toLocaleString()} mm`} />
      <Row
        label="Stress (dist / conc)"
        value={`${fmt(rail.distributed.bending_stress_mpa)} / ${fmt(rail.concentrated.bending_stress_mpa)} MPa`}
        fail={!rail.distributed.stress_passed}
      />
      <Row
        label="Allow. stress"
        value={`${fmt(rail.allowable_stress_mpa)} MPa`}
      />
      <Row
        label="Deflection (dist / conc)"
        value={`${fmt(rail.distributed.deflection_mm)} / ${fmt(rail.concentrated.deflection_mm)} mm`}
        fail={!rail.distributed.deflection_passed}
      />
      <Row label="Allow. deflection" value={`${fmt(rail.deflection_limit_mm)} mm`} />
      <Row label="Utilisation" value={`${fmt(rail.utilisation * 100, 1)} %`} />
    </div>
  );
}

function LegSection({ leg }: { leg: LegCheck }) {
  return (
    <div className="rounded border border-border bg-bg p-3 text-xs font-mono space-y-1">
      <p className="text-muted mb-1">Leg buckling (est.)</p>
      <Row label="F leg" value={`${fmt(leg.f_leg_n, 0)} N`} />
      {leg.buckling_status === "evaluated" && leg.p_cr_allowable_n != null ? (
        <>
          <Row label="P_cr allowable" value={`${fmt(leg.p_cr_allowable_n, 0)} N`} />
          <Row
            label="Buckling"
            value={leg.buckling_passed ? "Pass" : "Fail"}
            fail={!leg.buckling_passed}
          />
        </>
      ) : (
        <Row
          label="Buckling"
          value={`Not evaluated${leg.buckling_not_evaluated_reason ? ` — ${leg.buckling_not_evaluated_reason}` : ""}`}
        />
      )}
      <Row
        label="Compressive stress"
        value={
          leg.compressive_stress_status === "not_evaluated"
            ? "Not evaluated"
            : leg.compressive_stress_passed === true
            ? "Pass"
            : "Fail"
        }
        fail={leg.compressive_stress_passed === false}
      />
    </div>
  );
}

export function LoadCheck({ checkReport }: LoadCheckProps) {
  const { load, collision, connectivity, leg_check, tipping } = checkReport;
  const gov = load.governing_rail;

  // For shelf units, show governing rail only (not all rails — there could be many)
  const showAllRails = false;

  return (
    <div className="flex flex-col gap-3">
      {load.status === "not_evaluated" && load.not_evaluated_reason && (
        <p className="text-xs text-muted">{load.not_evaluated_reason}</p>
      )}

      {gov && (
        <RailCard
          rail={gov}
          governing
        />
      )}

      {showAllRails && load.all_rails
        .filter((r) => r.bar_index !== gov?.bar_index)
        .map((r) => (
          <RailCard key={r.bar_index} rail={r} governing={false} />
        ))}

      {leg_check && <LegSection leg={leg_check} />}

      {tipping?.warning && tipping.message && (
        <div className="rounded border border-warn/40 bg-warn/5 px-3 py-2 text-xs text-warn leading-relaxed">
          ⚠ {tipping.message}
        </div>
      )}

      {gov && !gov.concentrated.passed && (
        <p className="text-xs text-warn leading-relaxed">
          ⚠ Concentrated-load case fails — the frame may not handle a single
          heavy load at one point, even though the distributed case passes.
          Distribute the load or reduce it.
        </p>
      )}

      <p className="text-xs text-muted">
        These are estimates with a {load.safety_factor}× safety factor.
        The headline (Pass/Fail) assumes the load is spread evenly.
        Verify before building.
      </p>

      {checkReport.not_covered.length > 0 && (
        <details className="text-xs text-muted">
          <summary className="cursor-pointer select-none hover:text-text">
            What these estimates do not cover
          </summary>
          <ul className="mt-1 ml-3 list-disc space-y-0.5 leading-relaxed">
            {checkReport.not_covered.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </details>
      )}

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
