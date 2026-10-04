"use client";

import type { AssistantCard as AssistantCardType, FrameSpec } from "@/lib/types";
import { Spinner } from "@/components/ui/Spinner";

interface Props {
  card: AssistantCardType;
  spec: FrameSpec | null;
  onRestore?: (spec: FrameSpec) => void;
}

function fieldLabel(raw: string): string {
  return raw.replace(/_mm$|_kg$/, "").replace(/_/g, " ");
}

export function AssistantCard({ card, spec, onRestore }: Props) {
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
