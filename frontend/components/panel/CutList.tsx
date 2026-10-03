import type { CutListRow } from "@/lib/types";

interface CutListProps {
  rows: CutListRow[];
  /** Called with the hovered row's length, or null when the pointer leaves. */
  onRowHover?: (lengthMm: number | null) => void;
}

export function CutList({ rows, onRowHover }: CutListProps) {
  const grandTotal = rows.reduce((sum, r) => sum + r.total_mm, 0);

  return (
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
        </tfoot>
      </table>
    </div>
  );
}
