interface SpinnerProps {
  size?: "sm" | "md";
  className?: string;
}

export function Spinner({ size = "md", className = "" }: SpinnerProps) {
  const sz = size === "sm" ? "h-4 w-4 border-2" : "h-5 w-5 border-2";
  return (
    <span
      role="status"
      aria-label="Loading"
      className={`inline-block rounded-full border-current border-r-transparent animate-spin ${sz} ${className}`}
    />
  );
}
