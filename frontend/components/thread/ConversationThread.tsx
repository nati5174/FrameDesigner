"use client";

import { useEffect, useRef } from "react";
import type { FrameSpec, ThreadEntry } from "@/lib/types";
import { AssistantCard } from "@/components/thread/AssistantCard";

interface Props {
  entries: ThreadEntry[];
  onRestoreSpec?: (spec: FrameSpec) => void;
}

export function ConversationThread({ entries, onRestoreSpec }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [entries.length]);

  if (entries.length === 0) return null;

  return (
    <div className="flex flex-col gap-3 overflow-y-auto px-3 py-3">
      {entries.map((entry, i) => {
        if (entry.role === "user") {
          return (
            <div key={i} className="flex justify-end">
              <div className="max-w-[80%] rounded-lg bg-accent text-accent-fg px-3 py-2 text-sm">
                {entry.text}
              </div>
            </div>
          );
        }
        return (
          <div key={i} className="flex justify-start">
            <div className="w-full max-w-[90%]">
              <AssistantCard
                card={entry.card}
                spec={entry.spec}
                onRestore={onRestoreSpec}
              />
            </div>
          </div>
        );
      })}
      <div ref={bottomRef} />
    </div>
  );
}
