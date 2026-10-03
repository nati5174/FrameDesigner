interface FrameViewerPlaceholderProps {
  hasFrame: boolean;
}

export function FrameViewerPlaceholder({ hasFrame }: FrameViewerPlaceholderProps) {
  return (
    <div
      aria-label="Frame preview — 3D viewer coming in Stage B"
      className="
        flex h-full w-full items-center justify-center
        rounded-lg border border-border bg-surface
        text-muted text-sm select-none
      "
    >
      {hasFrame ? (
        <span>3D viewer coming in Stage B</span>
      ) : (
        <span>Enter a description above to generate a frame</span>
      )}
    </div>
  );
}
