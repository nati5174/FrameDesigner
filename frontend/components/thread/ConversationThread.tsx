"use client";

import { useEffect, useRef } from "react";
import type { FrameSpec, ThreadEntry } from "@/lib/types";
import { AssistantCard } from "@/components/thread/AssistantCard";

interface Props {
  entries: ThreadEntry[];
  onRestoreSpec?: (spec: FrameSpec) => void;
  onChip?: (text: string) => void;
}

export function ConversationThread({ entries, onRestoreSpec, onChip }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [entries.length]);

  if (entries.length === 0) return null;

  // Find the index of the last assistant entry for isLatest
  const lastAssistantIdx = entries.reduce(
    (last, e, i) => (e.role === "assistant" ? i : last),
    -1,
  );

  return (
    <div className="flex flex-col gap-3 overflow-y-auto px-3 py-3">
      {entries.map((entry, i) => {
        if (entry.role === "user") {
          return (
            <div key={i} className="flex justify-end">
              <div className="max-w-[80%] bg-ink text-surface px-3 py-2 text-sm">
                {entry.text}
              </div>
            </div>
          );
        }
        const isLatest = i === lastAssistantIdx;
        // Restore only makes sense on non-latest cards (go back to an earlier design)
        const canRestore = !isLatest && entry.spec != null;
        return (
          <div key={i} className="flex justify-start">
            <div className="w-full">
              <AssistantCard
                card={entry.card}
                spec={entry.spec}
                onRestore={canRestore ? onRestoreSpec : undefined}
                onChip={isLatest ? onChip : undefined}
                isLatest={isLatest}
              />
            </div>
          </div>
        );
      })}
      <div ref={bottomRef} />
    </div>
  );
}
