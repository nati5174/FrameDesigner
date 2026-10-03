"use client";

import { useState } from "react";

interface CollapsibleSectionProps {
  title: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}

export function CollapsibleSection({
  title,
  defaultOpen = true,
  children,
}: CollapsibleSectionProps) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <section className="border-b border-border last:border-b-0">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="
          flex w-full items-center justify-between px-4 py-3
          text-sm font-medium text-text hover:bg-border/30
          transition-colors
        "
      >
        <span>{title}</span>
        <span
          aria-hidden="true"
          className={`text-muted text-xs transition-transform ${open ? "rotate-0" : "-rotate-90"}`}
        >
          ▾
        </span>
      </button>
      {open && <div className="px-4 pb-4">{children}</div>}
    </section>
  );
}
