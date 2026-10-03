"use client";

import { Spinner } from "@/components/ui/Spinner";
import { ErrorBanner } from "@/components/ui/ErrorBanner";

interface PromptBarProps {
  value: string;
  onChange: (text: string) => void;
  onSubmit: () => void;
  loading: boolean;
  error: string | null;
  onDismissError: () => void;
}

export function PromptBar({
  value,
  onChange,
  onSubmit,
  loading,
  error,
  onDismissError,
}: PromptBarProps) {
  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (value.trim()) onSubmit();
  }

  return (
    <div className="flex flex-col gap-2">
      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="Describe your frame — e.g. workbench 1500 × 700 mm, 900 mm tall, holds 80 kg"
          aria-label="Frame description"
          disabled={loading}
          className="
            flex-1 min-w-0 rounded-md border border-border bg-surface px-3 py-2
            text-sm text-text placeholder:text-muted
            disabled:opacity-60
          "
        />
        <button
          type="submit"
          disabled={loading || !value.trim()}
          className="
            flex items-center gap-2 rounded-md bg-accent px-4 py-2
            text-sm font-medium text-accent-fg
            hover:bg-accent-hover disabled:opacity-50
            transition-colors shrink-0
          "
        >
          {loading && <Spinner size="sm" />}
          {loading ? "Parsing…" : "Generate"}
        </button>
      </form>
      {error && <ErrorBanner message={error} onDismiss={onDismissError} />}
    </div>
  );
}
