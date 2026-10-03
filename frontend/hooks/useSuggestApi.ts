"use client";

import { useCallback, useRef } from "react";
import type { FixCandidate, FrameSpec } from "@/lib/types";

interface SuggestRequest {
  spec: FrameSpec;
  original_request: string;
}

/**
 * Fire-and-forget POST /suggest.
 *
 * Stale-response guard: the caller passes a frameId. The callback is only
 * invoked when the response belongs to the frame currently displayed.
 * The current frameId is tracked in a ref so that closure captures do not
 * need to be stale.
 */
export function useSuggestApi() {
  const abortRef = useRef<AbortController | null>(null);
  const currentFrameId = useRef<number>(0);

  const setFrameId = useCallback((id: number) => {
    currentFrameId.current = id;
  }, []);

  const suggest = useCallback(
    async (
      spec: FrameSpec,
      originalRequest: string,
      frameId: number,
      onResult: (candidates: FixCandidate[]) => void
    ): Promise<void> => {
      // Cancel any in-flight suggest request
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      const body: SuggestRequest = { spec, original_request: originalRequest };

      try {
        const res = await fetch("/suggest", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
          signal: controller.signal,
        });
        if (!res.ok) return;
        const json = await res.json() as { suggestions: FixCandidate[] };
        // Only apply if this response belongs to the frame currently shown
        if (currentFrameId.current === frameId) {
          onResult(json.suggestions);
        }
      } catch {
        // /suggest failures are silent — template text stays
      }
    },
    []
  );

  return { suggest, setFrameId };
}
