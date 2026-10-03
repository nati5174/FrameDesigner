import type { FixCandidate } from "@/lib/types";

const FIX_LABEL: Record<FixCandidate["fix_type"], string> = {
  reduce_span_width: "Reduce width",
  reduce_span_depth: "Reduce depth",
  reduce_load:       "Reduce load",
  centre_legs:       "Add centre legs",
};

interface SuggestionCardProps {
  candidate: FixCandidate;
  canUndo: boolean;
  onApply: (candidate: FixCandidate) => void;
  onUndo: () => void;
}

export function SuggestionCard({
  candidate,
  canUndo,
  onApply,
  onUndo,
}: SuggestionCardProps) {
  const label = FIX_LABEL[candidate.fix_type];

  return (
    <div className="rounded-md border border-border bg-surface p-3 flex flex-col gap-2">
      <div className="flex items-start justify-between gap-2">
        <span className="text-sm font-medium text-text">{label}</span>
        {candidate.concentrated_warning_remains && (
          <span className="text-xs text-warn shrink-0">warn remains</span>
        )}
      </div>
      <p className="text-xs text-muted leading-relaxed">{candidate.trade_off}</p>
      <div className="flex gap-2 mt-1">
        <button
          type="button"
          onClick={() => onApply(candidate)}
          className="
            flex-1 rounded border border-accent px-3 py-1
            text-xs font-medium text-accent
            hover:bg-accent hover:text-accent-fg
            transition-colors
          "
        >
          Apply
        </button>
        {canUndo && (
          <button
            type="button"
            onClick={onUndo}
            className="
              rounded border border-border px-3 py-1
              text-xs text-muted hover:text-text hover:border-text
              transition-colors
            "
          >
            Undo
          </button>
        )}
      </div>
    </div>
  );
}
