// CSV export helpers — build and download cut list and parts list CSV files.
// All values are copied from the API response; no domain numbers are recomputed here.

import type { CutListRow, CutPlanResponse, FrameSpec, PartsListRow } from "@/lib/types";

// ─── Helpers ──────────────────────────────────────────────────────────────────

export function csvEscape(v: string | number | null | undefined): string {
  if (v == null) return "";
  const s = String(v);
  if (s.includes(",") || s.includes('"') || s.includes("\n") || s.includes("\r")) {
    return `"${s.replace(/"/g, '""')}"`;
  }
  return s;
}

function csvRow(...fields: (string | number | null | undefined)[]): string {
  return fields.map(csvEscape).join(",");
}

function designSummary(spec: FrameSpec): string {
  const load =
    spec.target_load_kg != null
      ? `load ${spec.target_load_kg} kg`
      : spec.load_per_level_kg != null
      ? `${spec.load_per_level_kg} kg/level`
      : null;
  return [
    spec.frame_type,
    `${spec.width_mm} x ${spec.depth_mm} x ${spec.height_mm} mm`,
    load,
    spec.profile_series,
  ]
    .filter(Boolean)
    .join(", ");
}

const DISCLAIMER =
  "Load results are estimates, not certified engineering. Prices read from the vendor site on the catalog date; check before ordering.";

const HARDWARE_NOTE =
  "One 2-hole inside corner bracket per rail end, 2 bolts and 2 T-nuts; minimum to assemble. Joint strength not checked.";

const CATALOG_SOURCE_DATE = "2026-10-04";

function commentHeaders(spec: FrameSpec, catalogVersion: string, today: string): string[] {
  return [
    "# Frame Designer",
    `# Design: ${designSummary(spec)}`,
    `# Date: ${today}`,
    `# Catalog: ${catalogVersion} (prices read ${CATALOG_SOURCE_DATE})`,
    `# Hardware: ${HARDWARE_NOTE}`,
    `# ${DISCLAIMER}`,
  ];
}

function triggerDownload(filename: string, content: string): void {
  const blob = new Blob([content], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// ─── Cut list CSV ─────────────────────────────────────────────────────────────
// Columns: profile_id, length_mm, qty, unit_cost_usd, line_cost_usd
// (role is not included — the cut list groups bars by profile+length,
//  so role is not available in the API response for cut list rows)

export function buildCutListCsv(
  spec: FrameSpec,
  rows: CutListRow[],
  totalCostUsd: number | null,
  catalogVersion = "v4",
  today = new Date().toISOString().slice(0, 10),
): { content: string; filename: string } {
  const lines: string[] = [
    ...commentHeaders(spec, catalogVersion, today),
    "",
    csvRow("profile_id", "length_mm", "qty", "unit_cost_usd", "line_cost_usd"),
    ...rows.map((r) => {
      const unitCost = r.cost_usd != null ? (r.cost_usd / r.qty).toFixed(2) : null;
      const lineCost = r.cost_usd != null ? r.cost_usd.toFixed(2) : null;
      return csvRow(r.profile_id, r.length_mm, r.qty, unitCost, lineCost);
    }),
    "",
    csvRow("", "Total (bars + cuts)", "", "", totalCostUsd != null ? totalCostUsd.toFixed(2) : "n/a"),
  ];

  return {
    content: lines.join("\n"),
    filename: `frame-cut-list-${spec.width_mm}x${spec.depth_mm}x${spec.height_mm}.csv`,
  };
}

export function downloadCutListCsv(
  spec: FrameSpec,
  rows: CutListRow[],
  totalCostUsd: number | null,
  catalogVersion = "v4",
): void {
  const { content, filename } = buildCutListCsv(spec, rows, totalCostUsd, catalogVersion);
  triggerDownload(filename, content);
}

// ─── Parts list CSV ───────────────────────────────────────────────────────────
// Columns: part_number, description, qty, unit_price_usd, line_total_usd, source_url
// Bars are listed first (from cut_list rows), then hardware, then summary rows.

export function buildPartsListCsv(
  spec: FrameSpec,
  cutListRows: CutListRow[],
  partsRows: PartsListRow[],
  barsCostUsd: number | null,
  hardwareCostUsd: number | null,
  totalCostUsd: number | null,
  hardwarePriced: boolean,
  catalogVersion = "v4",
  today = new Date().toISOString().slice(0, 10),
): { content: string; filename: string } {
  const notPricedNote = hardwarePriced
    ? []
    : ["# bars and cuts only, hardware not priced"];

  const lines: string[] = [
    ...commentHeaders(spec, catalogVersion, today),
    ...notPricedNote,
    "",
    csvRow("part_number", "description", "qty", "unit_price_usd", "line_total_usd", "source_url"),
    // Bar rows
    ...cutListRows.map((r) => {
      const unitCost = r.cost_usd != null ? (r.cost_usd / r.qty).toFixed(2) : null;
      const lineCost = r.cost_usd != null ? r.cost_usd.toFixed(2) : null;
      return csvRow(r.profile_id, `bar ${r.length_mm} mm`, r.qty, unitCost, lineCost, "");
    }),
    csvRow("", "Bars + cuts", "", "", barsCostUsd != null ? barsCostUsd.toFixed(2) : "n/a", ""),
  ];

  if (hardwarePriced && partsRows.length > 0) {
    lines.push("");
    partsRows.forEach((r) => {
      lines.push(
        csvRow(
          r.part_number,
          r.description,
          r.qty,
          r.unit_price_usd.toFixed(2),
          r.line_total_usd.toFixed(2),
          r.source_url,
        ),
      );
    });
    lines.push(
      csvRow("", "Hardware", "", "", hardwareCostUsd != null ? hardwareCostUsd.toFixed(2) : "n/a", ""),
    );
  }

  if (totalCostUsd != null) {
    lines.push(csvRow("", "Total", "", "", totalCostUsd.toFixed(2), ""));
  }

  return {
    content: lines.join("\n"),
    filename: `frame-parts-list-${spec.width_mm}x${spec.depth_mm}x${spec.height_mm}.csv`,
  };
}

// ─── Cut plan CSV ─────────────────────────────────────────────────────────────
// Columns: stock_bar, piece_index, length_mm, label
// One section per profile; summary row per profile; footer note.

export function buildCutPlanCsv(
  spec: FrameSpec,
  plan: CutPlanResponse,
  catalogVersion = "v4",
  today = new Date().toISOString().slice(0, 10),
): { content: string; filename: string } {
  const lines: string[] = [
    ...commentHeaders(spec, catalogVersion, today),
    `# Cut plan: stock ${plan.stock_length_mm} mm, kerf ${plan.kerf_mm} mm`,
    `# Each piece uses its length plus one kerf (saw blade width).`,
    "",
  ];

  for (const profile of plan.profiles) {
    lines.push(csvRow(`Profile: ${profile.profile_id}`));
    lines.push(csvRow("stock_bar", "piece_index", "length_mm", "label"));
    for (let i = 0; i < profile.stock_bars.length; i++) {
      const bar = profile.stock_bars[i];
      for (let j = 0; j < bar.pieces.length; j++) {
        const p = bar.pieces[j];
        lines.push(csvRow(i + 1, j + 1, p.length_mm, p.label));
      }
      lines.push(csvRow(i + 1, "offcut", bar.offcut_mm, "offcut"));
    }
    if (profile.does_not_fit.length > 0) {
      lines.push(csvRow("", "DOES NOT FIT (piece longer than stock)", "", ""));
      for (const p of profile.does_not_fit) {
        lines.push(csvRow("", "", p.length_mm, p.label));
      }
    }
    const optimality = profile.is_optimal ? "fewest bars possible" : "may not be the minimum";
    lines.push(
      csvRow(
        "",
        `${profile.total_stock_bars} stock bars to buy`,
        `${profile.waste_pct.toFixed(1)}% waste`,
        optimality,
      ),
    );
    lines.push("");
  }

  return {
    content: lines.join("\n"),
    filename: `frame-cut-plan-${spec.width_mm}x${spec.depth_mm}x${spec.height_mm}.csv`,
  };
}

export function downloadCutPlanCsv(
  spec: FrameSpec,
  plan: CutPlanResponse,
  catalogVersion = "v4",
): void {
  const { content, filename } = buildCutPlanCsv(spec, plan, catalogVersion);
  triggerDownload(filename, content);
}

export function downloadPartsListCsv(
  spec: FrameSpec,
  cutListRows: CutListRow[],
  partsRows: PartsListRow[],
  barsCostUsd: number | null,
  hardwareCostUsd: number | null,
  totalCostUsd: number | null,
  hardwarePriced: boolean,
  catalogVersion = "v4",
): void {
  const { content, filename } = buildPartsListCsv(
    spec,
    cutListRows,
    partsRows,
    barsCostUsd,
    hardwareCostUsd,
    totalCostUsd,
    hardwarePriced,
    catalogVersion,
  );
  triggerDownload(filename, content);
}
