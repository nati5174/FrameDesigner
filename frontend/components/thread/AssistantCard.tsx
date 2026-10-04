"use client";

import type {
  AssistantCard as AssistantCardType,
  FixCandidate,
  FrameResponse,
  FrameSpec,
} from "@/lib/types";
import { Spinner } from "@/components/ui/Spinner";

interface Props {
  card: AssistantCardType;
  spec: FrameSpec | null;
  onRestore?: (spec: FrameSpec) => void;
  onChip?: (text: string) => void;
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

export function AssistantCard({ card, spec, onRestore, onChip }: Props) {
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
        ? "bg-accent text-accent-fg"
        : "bg-emerald-600 text-white dark:bg-emerald-500";
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
              {card.changes.map((c) => fieldLabel(c.field)).join(", ")} changed
            </span>
          )}
          {spec && onRestore && (
            <button
              type="button"
              onClick={() => onRestore(spec)}
              className="ml-auto text-xs text-accent hover:underline"
            >
              Restore
            </button>
          )}
        </div>

        {card.frameData?.check_report && (
          <div className="px-3 py-2 text-xs text-muted">
            Load check:{" "}
            <span
              className={
                card.frameData.check_report.passed
                  ? "text-emerald-600 dark:text-emerald-400"
                  : "text-red-600 dark:text-red-400"
              }
            >
              {card.frameData.check_report.passed ? "OK" : "Failed"}
            </span>
          </div>
        )}

        {card.type === "new_design" && card.defaults.length > 0 && (
          <div className="px-3 py-1.5 text-xs text-muted border-t border-border">
            Defaults applied: {card.defaults.join(", ")}
          </div>
        )}

        {onChip && card.frameData && (
          <div className="flex flex-wrap gap-1.5 px-3 py-2 border-t border-border">
            {nextStepChips(card.frameData, card.spec).map((chip) => (
              <button
                key={chip}
                type="button"
                data-testid="next-step-chip"
                onClick={() => onChip(chip)}
                className="rounded-full border border-border bg-background px-2.5 py-1 text-xs text-foreground hover:bg-accent hover:text-accent-fg transition-colors"
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
