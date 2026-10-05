import type { CutListRow, FrameSpec, PartsListRow } from "@/lib/types";
import { downloadPartsListCsv } from "@/lib/csvExport";
import { usd } from "@/lib/labels";

interface PartsListProps {
  rows: PartsListRow[];
  hardwareCostUsd: number | null;
  hardwareWeightKg: number | null;
  barsCostUsd: number | null;
  barsWeightKg: number | null;
  totalCostUsd: number | null;
  totalWeightKg: number | null;
  hardwarePriced: boolean;
  /** When provided (with cutListRows), enables the "Download parts list (CSV)" button. */
  spec?: FrameSpec | null;
  cutListRows?: CutListRow[];
}

export function PartsList({
  rows,
  hardwareCostUsd,
  hardwareWeightKg,
  barsCostUsd,
  barsWeightKg,
  totalCostUsd,
  totalWeightKg,
  hardwarePriced,
  spec,
  cutListRows,
}: PartsListProps) {
  if (!hardwarePriced) {
    return (
      <div className="flex flex-col gap-2">
        <p className="text-xs text-muted leading-snug">
          Hardware pricing not available for this profile series.
        </p>
        {spec && cutListRows && (
          <button
            type="button"
            onClick={() =>
              downloadPartsListCsv(spec, cutListRows, [], barsCostUsd, null, null, false)
            }
            className="self-start text-xs text-muted underline decoration-dotted hover:text-text transition-colors"
          >
            Download parts list (CSV)
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {/* Parts table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm font-mono">
          <thead>
            <tr className="border-b border-border text-left text-xs text-muted">
              <th className="pb-1 pr-2 font-medium">Part</th>
              <th className="pb-1 pr-2 font-medium">Description</th>
              <th className="pb-1 pr-2 font-medium text-right">Qty</th>
              <th className="pb-1 pr-2 font-medium text-right">Unit</th>
              <th className="pb-1 font-medium text-right">Total</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr
                key={i}
                className="border-b border-border/50 last:border-b-0"
              >
                <td className="py-1 pr-2 text-text whitespace-nowrap">
                  <a
                    href={row.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="underline decoration-dotted hover:text-text transition-colors"
                  >
                    {row.part_number}
                  </a>
                </td>
                <td className="py-1 pr-2 text-muted text-xs leading-tight">
                  {row.description}
                </td>
                <td className="py-1 pr-2 text-right text-muted">
                  {row.qty}
                </td>
                <td className="py-1 pr-2 text-right text-muted">
                  ${usd(row.unit_price_usd)}
                </td>
                <td className="py-1 text-right text-text">
                  ${usd(row.line_total_usd)}
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <td colSpan={4} className="pt-2 text-xs text-muted">
                Hardware total
              </td>
              <td className="pt-2 text-right text-sm font-medium text-text">
                {hardwareCostUsd != null
                  ? `$${usd(hardwareCostUsd)}`
                  : <span className="text-muted text-xs font-normal">n/a</span>
                }
              </td>
            </tr>
            {hardwareWeightKg != null && (
              <tr>
                <td colSpan={4} className="pt-1 text-xs text-muted">
                  Hardware weight
                </td>
                <td className="pt-1 text-right text-sm font-medium text-text">
                  {hardwareWeightKg.toFixed(3)} kg
                </td>
              </tr>
            )}
          </tfoot>
        </table>
      </div>

      {/* Cost breakdown */}
      {barsCostUsd != null && (
        <div className="border-t border-border pt-2 text-xs font-mono">
          <div className="flex justify-between text-muted">
            <span>Bars + cuts</span>
            <span>${usd(barsCostUsd)}</span>
          </div>
          <div className="flex justify-between text-muted">
            <span>Hardware</span>
            <span>
              {hardwareCostUsd != null
                ? `$${usd(hardwareCostUsd)}`
                : "n/a"}
            </span>
          </div>
          {totalCostUsd != null && (
            <div className="flex justify-between font-semibold text-text mt-1 border-t border-border pt-1">
              <span>Total</span>
              <span>${usd(totalCostUsd)}</span>
            </div>
          )}
          {totalWeightKg != null && (
            <div className="flex justify-between text-muted mt-1">
              <span>Total weight</span>
              <span>{totalWeightKg.toFixed(2)} kg</span>
            </div>
          )}
          {barsWeightKg != null && totalWeightKg == null && (
            <div className="flex justify-between text-muted mt-1">
              <span>Weight (bars only)</span>
              <span>{barsWeightKg.toFixed(2)} kg</span>
            </div>
          )}
        </div>
      )}

      <p className="text-xs text-muted leading-snug">
        One 2-hole inside corner bracket per rail end. Prices read 2026-10-05 from{" "}
        <a
          href="https://8020.net"
          target="_blank"
          rel="noopener noreferrer"
          className="underline decoration-dotted hover:text-accent transition-colors"
        >
          8020.net
        </a>
        , automated read, not confirmed by a person — except bolt 11-8318 price confirmed
        by a person 2026-10-05. Excludes shipping and tax.
      </p>

      {spec && cutListRows && (
        <button
          type="button"
          onClick={() =>
            downloadPartsListCsv(
              spec,
              cutListRows,
              rows,
              barsCostUsd,
              hardwareCostUsd,
              totalCostUsd,
              hardwarePriced,
            )
          }
          className="self-start text-xs text-muted underline decoration-dotted hover:text-text transition-colors"
        >
          Download parts list (CSV)
        </button>
      )}
    </div>
  );
}
