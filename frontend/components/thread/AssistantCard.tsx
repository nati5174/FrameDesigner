"use client";

import type {
  AssistantCard as AssistantCardType,
  FieldChange,
  FixCandidate,
  FrameResponse,
  FrameSpec,
} from "@/lib/types";
import { Spinner } from "@/components/ui/Spinner";
import { StatusBadge } from "@/components/StatusBadge";
import { formatFrameType } from "@/lib/labels";

interface Props {
  card: AssistantCardType;
  spec: FrameSpec | null;
  onRestore?: (spec: FrameSpec) => void;
  onChip?: (text: string) => void;
  /** True for the most recent assistant entry. Earlier cards render compact. */
  isLatest?: boolean;
}

// ── Next-step chip generation ─────────────────────────────────────────────────

function chipFromSuggestion(s: FixCandidate): string {
  switch (s.fix_type) {
    case "reduce_span_width":
      return `reduce width to ${s.spec.width_mm} mm`;
    case "reduce_span_depth":
      return `reduce depth to ${s.spec.depth_mm} mm`;
    case "reduce_load":
      return s.spec.target_load_kg != null
        ? `reduce load to ${s.spec.target_load_kg} kg`
        : `reduce load per level to ${s.spec.load_per_level_kg} kg`;
    case "reduce_load_per_level":
      return `reduce load per level to ${s.spec.load_per_level_kg} kg`;
    case "centre_legs":
      return "add centre legs";
    case "cheaper_profile":
      return `use ${s.spec.profile_series}`;
  }
}

function nextStepChips(frameData: FrameResponse, spec: FrameSpec): string[] {
  const load = frameData.check_report.load;
  const loadFailed = !load.passed;
  const concentratedWarns =
    load.governing_rail?.concentrated.passed === false;

  if ((loadFailed || concentratedWarns) && frameData.suggestions.length > 0) {
    return frameData.suggestions.slice(0, 3).map(chipFromSuggestion);
  }

  // Common edit chips — skip ones that don't apply
  const chips: string[] = [];
  chips.push("make it 100 mm taller");
  if (spec.frame_type === "table" && spec.shelf_height_mm == null) {
    chips.push("add a shelf");
  }
  if (!spec.centre_legs) {
    chips.push("add centre legs");
  }
  return chips.slice(0, 3);
}

function fieldLabel(raw: string): string {
  return raw.replace(/_mm$|_kg$/, "").replace(/_/g, " ");
}

function fieldUnit(key: string): string {
  if (key.endsWith("_mm")) return " mm";
  if (key.endsWith("_kg")) return " kg";
  return "";
}

function formatValue(field: string, val: unknown): string {
  if (field === "frame_type" && typeof val === "string") return formatFrameType(val);
  return String(val);
}

function formatChange(c: FieldChange): string {
  const label = fieldLabel(c.field);
  const cap = label.charAt(0).toUpperCase() + label.slice(1);
  const unit = fieldUnit(c.field);
  if (c.old != null && c.new != null) {
    return `${cap} ${formatValue(c.field, c.old)}${unit} → ${formatValue(c.field, c.new)}${unit}`;
  }
  return `${cap} → ${formatValue(c.field, c.new)}${unit}`;
}

/**
 * Converts an API default string like "height_mm=900" into
 * a human-readable label like "Height 900 mm (default)".
 */
function formatDefault(raw: string): string {
  const eq = raw.indexOf("=");
  if (eq === -1) return raw;
  const key = raw.slice(0, eq);
  const val = raw.slice(eq + 1);
  const label = fieldLabel(key);
  const unit = key.endsWith("_mm") ? " mm" : key.endsWith("_kg") ? " kg" : "";
  return `${label.charAt(0).toUpperCase()}${label.slice(1)} ${val}${unit} (default)`;
}

function specSummary(spec: FrameSpec): string {
  const parts = [
    `${spec.width_mm} × ${spec.depth_mm} × ${spec.height_mm} mm`,
    spec.profile_series,
  ];
  if (spec.target_load_kg != null) parts.push(`${spec.target_load_kg} kg`);
  if (spec.load_per_level_kg != null) parts.push(`${spec.load_per_level_kg} kg/level`);
  return parts.join(" · ");
}

export function AssistantCard({ card, spec, onRestore, onChip, isLatest = true }: Props) {
  // ── Collapsed one-liner for earlier (non-latest) cards ─────────────────────
  if (!isLatest && (card.type === "new_design" || card.type === "edit" || card.type === "example")) {
    const frameData = card.type === "example" ? card.frameData : card.frameData;
    const checkReport = frameData?.check_report;
    const status = checkReport
      ? checkReport.passed ? (checkReport.load.governing_rail && !checkReport.load.governing_rail.concentrated.passed ? "⚠" : "✓") : "✕"
      : null;
    const dimSpec = card.type === "example" ? card.spec : card.spec;
    const dimSummary = dimSpec
      ? `${dimSpec.width_mm} × ${dimSpec.depth_mm} × ${dimSpec.height_mm} mm`
      : "";
    return (
      <div className="flex items-center justify-between gap-2 px-3 py-2 border border-border bg-surface text-xs font-mono text-muted">
        <span>
          {status && <span className="mr-1">{status}</span>}
          {dimSummary}
        </span>
        {onRestore && spec && (
          <button
            type="button"
            onClick={() => onRestore(spec)}
            className="shrink-0 text-xs text-muted hover:text-text transition-colors"
          >
            Restore
          </button>
        )}
      </div>
    );
  }

  if (card.type === "example") {
    return (
      <div className="rounded-lg border border-border bg-surface text-sm overflow-hidden">
        <div className="px-3 py-2 border-b border-border">
          <p className="text-sm text-text">{card.message}</p>
        </div>

        {card.frameData?.check_report && (
          <div className="px-3 py-2 border-b border-border">
            <StatusBadge checkReport={card.frameData.check_report} />
          </div>
        )}

        {onChip && card.frameData && (
          <div className="flex flex-wrap gap-1.5 px-3 py-2">
            {nextStepChips(card.frameData, card.spec).map((chip) => (
              <button
                key={chip}
                type="button"
                data-testid="next-step-chip"
                onClick={() => onChip(chip)}
                className="border border-border bg-surface px-2.5 py-1 text-xs text-muted hover:border-ink hover:text-text transition-colors"
              >
                {chip}
              </button>
            ))}
          </div>
        )}
      </div>
    );
  }

  if (card.type === "loading") {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-border bg-surface px-3 py-3 text-sm text-muted">
        <Spinner size="sm" />
        <span>Thinking…</span>
      </div>
    );
  }

  if (card.type === "new_design" || card.type === "edit") {
    const badgeClass =
      card.type === "new_design"
        ? "bg-ink text-surface"
        : "border border-border text-muted";
    const label = card.type === "new_design" ? "New design" : "Updated";

    return (
      <div className="rounded-lg border border-border bg-surface text-sm overflow-hidden">
        <div className="flex items-center gap-2 px-3 py-2 border-b border-border">
          <span
            data-testid="card-badge"
            className={`rounded px-2 py-0.5 text-xs font-medium ${badgeClass}`}
          >
            {label}
          </span>
          {card.changes.length > 0 && (
            <span className="text-muted text-xs">
              {card.changes.slice(0, 2).map(formatChange).join(", ")}
              {card.changes.length > 2 && ` +${card.changes.length - 2} more`}
            </span>
          )}
          {spec && onRestore && (
            <button
              type="button"
              onClick={() => onRestore(spec)}
              className="ml-auto text-xs text-muted hover:text-text"
            >
              Restore
            </button>
          )}
        </div>

        {/* specSummary hidden on latest — dimensions live in the viewer caption strip */}
        {card.type === "new_design" && !isLatest && (
          <div data-testid="spec-summary" className="px-3 py-1.5 text-xs text-muted border-b border-border">
            {specSummary(card.spec)}
          </div>
        )}

        {card.frameData?.check_report && (
          <div className="px-3 py-2 border-b border-border">
            <StatusBadge checkReport={card.frameData.check_report} />
          </div>
        )}

        {card.type === "new_design" && card.defaults.length > 0 && (
          <p className="px-3 py-1.5 text-xs text-muted border-b border-border">
            {card.defaults.map(formatDefault).join(" · ")}
          </p>
        )}

        {onChip && card.frameData && (
          <div className="flex flex-wrap gap-1.5 px-3 py-2 border-t border-border">
            {nextStepChips(card.frameData, card.spec).map((chip) => (
              <button
                key={chip}
                type="button"
                data-testid="next-step-chip"
                onClick={() => onChip(chip)}
                className="border border-border bg-surface px-2.5 py-1 text-xs text-muted hover:border-ink hover:text-text transition-colors"
              >
                {chip}
              </button>
            ))}
          </div>
        )}
      </div>
    );
  }

  if (card.type === "clarify") {
    const missingLabels = card.missing
      .map(fieldLabel)
      .join(", ");
    return (
      <div className="rounded-lg border border-amber-300 bg-amber-50 dark:border-amber-700 dark:bg-amber-900/20 px-3 py-3 text-sm">
        <p className="font-medium text-amber-800 dark:text-amber-200">
          More information needed
        </p>
        {card.missing.length > 0 && (
          <p className="mt-1 text-amber-700 dark:text-amber-300 text-xs">
            Missing: {missingLabels}
          </p>
        )}
      </div>
    );
  }

  if (card.type === "unsupported") {
    return (
      <div className="rounded-lg border border-border bg-surface px-3 py-3 text-sm text-muted">
        {card.message}
      </div>
    );
  }

  if (card.type === "error") {
    return (
      <div className="rounded-lg border border-red-300 bg-red-50 dark:border-red-700 dark:bg-red-900/20 px-3 py-3 text-sm text-red-700 dark:text-red-300">
        {card.message}
      </div>
    );
  }

  return null;
}
