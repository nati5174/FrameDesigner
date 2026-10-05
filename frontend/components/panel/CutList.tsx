import type { CutListRow } from "@/lib/types";

interface CutListProps {
  rows: CutListRow[];
  totalCostUsd?: number | null;
  totalWeightKg?: number | null;
  /** Called with the hovered row's length, or null when the pointer leaves. */
  onRowHover?: (lengthMm: number | null) => void;
}

export function CutList({ rows, totalCostUsd, totalWeightKg, onRowHover }: CutListProps) {
  const grandTotal = rows.reduce((sum, r) => sum + r.total_mm, 0);
  const hasCost = totalCostUsd != null;
  const hasWeight = totalWeightKg != null;

  return (
    <div className="flex flex-col gap-3">
      <div className="overflow-x-auto">
        <table className="w-full text-sm font-mono">
          <thead>
            <tr className="border-b border-border text-left text-xs text-muted">
              <th className="pb-1 pr-3 font-medium">Profile</th>
              <th className="pb-1 pr-3 font-medium text-right">Length</th>
              <th className="pb-1 pr-3 font-medium text-right">Qty</th>
              <th className="pb-1 font-medium text-right">Total</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr
                key={i}
                onMouseEnter={() => onRowHover?.(row.length_mm)}
                onMouseLeave={() => onRowHover?.(null)}
                className="
                  border-b border-border/50 last:border-b-0
                  cursor-default transition-colors hover:bg-accent/5
                "
              >
                <td className="py-1 pr-3 text-text">{row.profile_id}</td>
                <td className="py-1 pr-3 text-right text-text">
                  {row.length_mm.toLocaleString()} mm
                </td>
                <td className="py-1 pr-3 text-right text-muted">×{row.qty}</td>
                <td className="py-1 text-right text-muted">
                  {row.total_mm.toLocaleString()} mm
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <td colSpan={3} className="pt-2 text-xs text-muted">
                Total bar length
              </td>
              <td className="pt-2 text-right text-sm font-medium text-text">
                {grandTotal.toLocaleString()} mm
              </td>
            </tr>
            {hasWeight && (
              <tr>
                <td colSpan={3} className="pt-1 text-xs text-muted">
                  Total weight
                </td>
                <td className="pt-1 text-right text-sm font-medium text-text">
                  {totalWeightKg!.toFixed(2)} kg
                </td>
              </tr>
            )}
            <tr>
              <td colSpan={3} className="pt-1 text-xs text-muted">
                Bars only, USD
              </td>
              <td className="pt-1 text-right text-sm font-medium text-text">
                {hasCost
                  ? `$${totalCostUsd!.toFixed(2)}`
                  : <span className="text-muted text-xs font-normal">n/a</span>
                }
              </td>
            </tr>
          </tfoot>
        </table>
      </div>

      <p className="text-xs text-muted leading-snug">
        {hasCost
          ? "Bars only, USD. See Parts list below for brackets, fasteners, and total. Excludes shipping and tax. Prices read 2026-10-04."
          : "Cost not available — no price data for this profile series. Excludes brackets and fasteners, shipping and tax."
        }
      </p>
    </div>
  );
}
