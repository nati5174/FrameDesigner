"use client";

import { useState } from "react";
import type { FrameSpec, ThreadEntry } from "@/lib/types";
import { ConversationThread } from "@/components/thread/ConversationThread";

interface Props {
  entries: ThreadEntry[];
  onRestoreSpec: (spec: FrameSpec) => void;
  onChip: (text: string) => void;
}

/**
 * Mobile-only expandable bottom sheet that holds the conversation thread.
 * Collapsed: a 48-px handle shows the message count.
 * Expanded: slides up to 70 vh and renders the full thread.
 */
export function ThreadSheet({ entries, onRestoreSpec, onChip }: Props) {
  const [expanded, setExpanded] = useState(false);

  if (entries.length === 0) return null;

  const count = entries.length;

  return (
    <>
      {/* Backdrop — close on tap outside */}
      {expanded && (
        <div
          className="fixed inset-0 z-20 bg-black/30"
          onClick={() => setExpanded(false)}
          aria-hidden="true"
        />
      )}

      <div
        className={`
          fixed inset-x-0 bottom-0 z-30 flex flex-col
          bg-background border-t border-border rounded-t-xl shadow-xl
          overflow-hidden transition-[max-height] duration-300
          ${expanded ? "max-h-[70vh]" : "max-h-12"}
        `}
      >
        {/* Toggle handle */}
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          aria-label={expanded ? "Collapse thread" : "Expand thread"}
          className="flex items-center justify-between px-4 py-3 shrink-0 w-full text-left"
        >
          <span className="text-sm font-medium text-text">
            {count} message{count !== 1 ? "s" : ""}
          </span>
          <span className="text-xs text-muted" aria-hidden="true">
            {expanded ? "▾" : "▴"}
          </span>
        </button>

        {/* Thread content — only rendered when expanded to avoid layout cost */}
        <div className="flex-1 overflow-y-auto">
          <ConversationThread
            entries={entries}
            onRestoreSpec={onRestoreSpec}
            onChip={onChip}
          />
        </div>
      </div>
    </>
  );
}
