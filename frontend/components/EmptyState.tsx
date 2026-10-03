import { EXAMPLES } from "@/lib/examples";

interface EmptyStateProps {
  onSelect: (prompt: string) => void;
}

export function EmptyState({ onSelect }: EmptyStateProps) {
  return (
    <div className="flex h-full items-center justify-center">
      <div className="flex flex-col items-center gap-7 px-6 text-center max-w-md">
        <div className="flex flex-col gap-2">
          <h1 className="text-lg font-semibold text-text tracking-tight">
            Frame Designer
          </h1>
          <p className="text-sm text-muted leading-relaxed">
            Describe an aluminium T-slot frame and get a 3D view,
            cut list, and load estimate.
          </p>
        </div>

        <div className="flex flex-col gap-2 w-full items-center">
          <p className="text-xs text-muted">Try an example</p>
          <div className="flex flex-wrap gap-2 justify-center">
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
      </div>
    </div>
  );
}
