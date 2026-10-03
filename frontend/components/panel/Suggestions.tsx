import type { FixCandidate } from "@/lib/types";
import { SuggestionCard } from "@/components/panel/SuggestionCard";

interface SuggestionsProps {
  candidates: FixCandidate[];
  canUndo: boolean;
  onApply: (candidate: FixCandidate) => void;
  onUndo: () => void;
}

export function Suggestions({ candidates, canUndo, onApply, onUndo }: SuggestionsProps) {
  if (candidates.length === 0) return null;

  return (
    <div className="flex flex-col gap-2">
      <p className="text-xs text-muted">
        These fixes are verified — each one passes the load check.
      </p>
      {candidates.map((c, i) => (
        <SuggestionCard
          key={i}
          candidate={c}
          canUndo={canUndo}
          onApply={onApply}
          onUndo={onUndo}
        />
      ))}
    </div>
  );
}
