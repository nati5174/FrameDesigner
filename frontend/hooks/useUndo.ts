"use client";

import { useCallback, useState } from "react";
import type { FrameSpec } from "@/lib/types";

interface UseUndo {
  save: (spec: FrameSpec) => void;
  take: () => FrameSpec | null;
  canUndo: boolean;
}

/** Single-level undo for Apply. */
export function useUndo(): UseUndo {
  const [saved, setSaved] = useState<FrameSpec | null>(null);

  const save = useCallback((spec: FrameSpec) => {
    setSaved(spec);
  }, []);

  const take = useCallback((): FrameSpec | null => {
    const prev = saved;
    setSaved(null);
    return prev;
  }, [saved]);

  return { save, take, canUndo: saved !== null };
}
