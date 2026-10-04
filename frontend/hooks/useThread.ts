"use client";

import { useCallback, useEffect, useState } from "react";
import type { AssistantCard, FrameSpec, PartialSpec, ThreadEntry } from "@/lib/types";

const _STORAGE_KEY = "frame_designer_thread";

interface Persisted {
  entries: ThreadEntry[];
  currentSpec: FrameSpec | null;
  pending: PartialSpec | null;
}

function loadFromStorage(): Persisted {
  if (typeof window === "undefined") {
    return { entries: [], currentSpec: null, pending: null };
  }
  try {
    const raw = localStorage.getItem(_STORAGE_KEY);
    if (!raw) return { entries: [], currentSpec: null, pending: null };
    return JSON.parse(raw) as Persisted;
  } catch {
    return { entries: [], currentSpec: null, pending: null };
  }
}

function saveToStorage(data: Persisted): void {
  try {
    // Filter out loading entries before persisting
    const toSave: Persisted = {
      ...data,
      entries: data.entries.filter(
        (e) => !(e.role === "assistant" && e.card.type === "loading")
      ),
    };
    localStorage.setItem(_STORAGE_KEY, JSON.stringify(toSave));
  } catch {
    // localStorage may be unavailable (private mode quota exceeded, etc.)
  }
}

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
  // hydrated gates persistence — avoids writing empty state over saved data
  const [hydrated, setHydrated] = useState(false);

  // Load saved state after mount (keeps first render identical to server,
  // preventing a hydration mismatch). setState is intentional here — this is
  // the canonical pattern for a one-time post-mount sync from an external store.
  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    const saved = loadFromStorage();
    setEntries(saved.entries);
    setCurrentSpec(saved.currentSpec);
    setPending(saved.pending);
    setHydrated(true);
  }, []);
  /* eslint-enable react-hooks/set-state-in-effect */

  // Persist on every change, but only after the initial load
  useEffect(() => {
    if (!hydrated) return;
    saveToStorage({ entries, currentSpec, pending });
  }, [entries, currentSpec, pending, hydrated]);

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
    try {
      localStorage.removeItem(_STORAGE_KEY);
    } catch {
      // ignore
    }
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
