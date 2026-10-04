"use client";

import { useCallback, useState } from "react";
import type { AssistantCard, FrameSpec, PartialSpec, ThreadEntry } from "@/lib/types";

export interface UseThread {
  entries: ThreadEntry[];
  currentSpec: FrameSpec | null;
  pending: PartialSpec | null;
  addUserEntry: (text: string) => void;
  addLoadingEntry: () => void;
  resolveLastEntry: (
    card: AssistantCard,
    spec: FrameSpec | null,
    newPending: PartialSpec | null
  ) => void;
  restoreToSpec: (spec: FrameSpec) => void;
  clear: () => void;
}

export function useThread(): UseThread {
  const [entries, setEntries] = useState<ThreadEntry[]>([]);
  const [currentSpec, setCurrentSpec] = useState<FrameSpec | null>(null);
  const [pending, setPending] = useState<PartialSpec | null>(null);

  const addUserEntry = useCallback((text: string) => {
    setEntries((prev) => [...prev, { role: "user", text }]);
  }, []);

  const addLoadingEntry = useCallback(() => {
    setEntries((prev) => [
      ...prev,
      { role: "assistant", card: { type: "loading" }, spec: null },
    ]);
  }, []);

  const resolveLastEntry = useCallback(
    (
      card: AssistantCard,
      spec: FrameSpec | null,
      newPending: PartialSpec | null
    ) => {
      setEntries((prev) => {
        const next = [...prev];
        const i = next.length - 1;
        if (i >= 0 && next[i].role === "assistant") {
          next[i] = { role: "assistant", card, spec };
        }
        return next;
      });
      if (spec !== null) setCurrentSpec(spec);
      setPending(newPending);
    },
    []
  );

  const restoreToSpec = useCallback((spec: FrameSpec) => {
    setCurrentSpec(spec);
    setPending(null);
  }, []);

  const clear = useCallback(() => {
    setEntries([]);
    setCurrentSpec(null);
    setPending(null);
  }, []);

  return {
    entries,
    currentSpec,
    pending,
    addUserEntry,
    addLoadingEntry,
    resolveLastEntry,
    restoreToSpec,
    clear,
  };
}
