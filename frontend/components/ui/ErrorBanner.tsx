"use client";

interface ErrorBannerProps {
  message: string;
  onDismiss?: () => void;
}

export function ErrorBanner({ message, onDismiss }: ErrorBannerProps) {
  return (
    <div
      role="alert"
      className="flex items-start gap-2 rounded-md bg-surface border border-fail/30 px-3 py-2 text-fail text-sm"
    >
      <span aria-hidden="true" className="mt-0.5 shrink-0">✕</span>
      <span className="flex-1">{message}</span>
      {onDismiss && (
        <button
          onClick={onDismiss}
          aria-label="Dismiss error"
          className="shrink-0 text-muted hover:text-text"
        >
          ✕
        </button>
      )}
    </div>
  );
}
