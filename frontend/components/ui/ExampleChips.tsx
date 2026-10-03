"use client";

import { EXAMPLES } from "@/lib/examples";

interface ExampleChipsProps {
  onSelect: (prompt: string) => void;
}

export function ExampleChips({ onSelect }: ExampleChipsProps) {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-6 p-8 select-none">
      <p className="text-muted text-sm text-center">
        Try an example or describe your frame above
      </p>
      <div className="flex flex-wrap gap-3 justify-center max-w-lg">
        {EXAMPLES.map((ex) => (
          <button
            key={ex.prompt}
            onClick={() => onSelect(ex.prompt)}
            className="
              px-4 py-2 rounded-full border border-border bg-surface
              text-sm text-text hover:border-accent hover:text-accent
              transition-colors
            "
          >
            {ex.label}
          </button>
        ))}
      </div>
    </div>
  );
}
