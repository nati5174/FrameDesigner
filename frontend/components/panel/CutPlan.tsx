"use client";

import type { FrameSpec, ProfileCutPlan, StockBarPlan } from "@/lib/types";
import { downloadCutPlanCsv } from "@/lib/csvExport";
import { useCutPlan } from "@/hooks/useCutPlan";

// Hue values for cycling piece colors
const PIECE_HUES = [220, 150, 30, 280, 60, 190];

function pieceColor(i: number): string {
  return `hsl(${PIECE_HUES[i % PIECE_HUES.length]}, 65%, 52%)`;
}

interface BarStripProps {
  bar: StockBarPlan;
  stockLength: number;
  kerf: number;
}

function BarStrip({ bar, stockLength, kerf }: BarStripProps) {
  const showKerf = kerf > 0;
  // Only show an inline label when the piece is at least 8% of stock length
  const labelThreshold = stockLength * 0.08;

  return (
    <div
      className="flex w-full overflow-hidden rounded"
      style={{ height: "28px" }}
      aria-label={`Stock bar: ${bar.used_mm} mm used, ${bar.offcut_mm} mm offcut`}
    >
      {bar.pieces.map((piece, j) => {
        const pct = (piece.length_mm / stockLength) * 100;
        const kPct = (kerf / stockLength) * 100;
        const color = pieceColor(j);
        return (
          <div key={j} className="flex shrink-0">
            <div
              title={`${piece.length_mm} mm — ${piece.label}`}
              className="flex items-center justify-center overflow-hidden shrink-0"
              style={{
                width: `${pct}%`,
                background: color,
                color: "#fff",
                fontSize: "10px",
              }}
            >
              {piece.length_mm >= labelThreshold
                ? String(Math.round(piece.length_mm))
                : ""}
            </div>
            {showKerf && (
              <div
                title="kerf"
                className="shrink-0 bg-neutral-800 dark:bg-neutral-200"
                style={{ width: `${kPct}%`, minWidth: "2px" }}
              />
            )}
          </div>
        );
      })}
      {bar.offcut_mm > 0 && (
        <div
          title={`Offcut: ${bar.offcut_mm} mm`}
          className="grow flex items-center justify-end pr-1 overflow-hidden"
          style={{
            background: "repeating-linear-gradient(135deg, var(--color-border) 0px, var(--color-border) 2px, var(--color-surface) 2px, var(--color-surface) 8px)",
            fontSize: "10px",
            color: "var(--color-muted)",
          }}
        >
          {bar.offcut_mm >= stockLength * 0.08
            ? `${Math.round(bar.offcut_mm)}`
            : ""}
        </div>
      )}
    </div>
  );
}

interface ProfilePlanProps {
  profile: ProfileCutPlan;
  stockLength: number;
  kerf: number;
}

function ProfilePlan({ profile, stockLength, kerf }: ProfilePlanProps) {
  const optimality = profile.is_optimal ? "fewest bars possible" : "may not be the minimum";

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-baseline justify-between text-xs">
        <span className="font-medium text-text">{profile.profile_id}</span>
        <span className="text-muted">
          {profile.total_stock_bars} bar{profile.total_stock_bars !== 1 ? "s" : ""} ·{" "}
          {profile.waste_pct.toFixed(1)}% waste · {optimality}
        </span>
      </div>

      {profile.does_not_fit.length > 0 && (
        <p className="text-xs text-amber-600 dark:text-amber-400 leading-snug">
          {profile.does_not_fit.length} piece
          {profile.does_not_fit.length !== 1 ? "s" : ""} longer than stock:{" "}
          {profile.does_not_fit.map((p) => `${p.length_mm} mm`).join(", ")}
        </p>
      )}

      {profile.stock_bars.map((bar, i) => (
        <div key={i} className="flex items-center gap-2">
          <span className="text-xs text-muted font-mono w-4 shrink-0 text-right">
            {i + 1}
          </span>
          <div className="flex-1 min-w-0">
            <BarStrip bar={bar} stockLength={stockLength} kerf={kerf} />
          </div>
        </div>
      ))}
    </div>
  );
}

interface CutPlanProps {
  spec: FrameSpec;
}

export function CutPlan({ spec }: CutPlanProps) {
  const {
    stockLength,
    setStockLength,
    kerf,
    setKerf,
    result,
    loading,
    error,
    calculate,
  } = useCutPlan(spec);

  return (
    <div className="flex flex-col gap-3">
      {/* Inputs */}
      <div className="flex flex-col gap-2">
        <label className="flex flex-col gap-0.5">
          <span className="text-xs font-medium text-text">Stock length (mm)</span>
          <input
            type="number"
            min={500}
            max={8000}
            step={100}
            value={stockLength}
            onChange={(e) => setStockLength(Number(e.target.value))}
            className="
              w-full rounded border border-border bg-surface px-2 py-1
              text-sm font-mono text-text
              focus:border-accent focus:outline-none
            "
          />
          <span className="text-xs text-muted">
            your value; check your supplier and saw
          </span>
        </label>

        <label className="flex flex-col gap-0.5">
          <span className="text-xs font-medium text-text">Saw kerf (mm)</span>
          <input
            type="number"
            min={0}
            max={10}
            step={0.5}
            value={kerf}
            onChange={(e) => setKerf(Number(e.target.value))}
            className="
              w-full rounded border border-border bg-surface px-2 py-1
              text-sm font-mono text-text
              focus:border-accent focus:outline-none
            "
          />
          <span className="text-xs text-muted">
            your value; check your supplier and saw
          </span>
        </label>
      </div>

      <button
        type="button"
        onClick={calculate}
        disabled={loading}
        className="
          self-start rounded border border-border bg-surface px-3 py-1
          text-xs font-medium text-text
          hover:bg-border/30 disabled:opacity-50 transition-colors
        "
      >
        {loading ? "Calculating…" : "Calculate"}
      </button>

      {error && (
        <p className="text-xs text-red-600 dark:text-red-400">{error}</p>
      )}

      {result && (
        <>
          {result.profiles.map((profile) => (
            <ProfilePlan
              key={profile.profile_id}
              profile={profile}
              stockLength={result.stock_length_mm}
              kerf={result.kerf_mm}
            />
          ))}

          <button
            type="button"
            onClick={() => downloadCutPlanCsv(spec, result)}
            className="self-start text-xs text-muted underline decoration-dotted hover:text-text transition-colors"
          >
            Download cut plan (CSV)
          </button>
        </>
      )}

      <p className="text-xs text-muted leading-snug">
        Each piece uses its length plus one kerf (saw blade width).
      </p>
    </div>
  );
}
