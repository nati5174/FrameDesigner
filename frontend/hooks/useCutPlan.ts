"use client";

import { useCallback, useRef, useState } from "react";
import type { CutPlanResponse, FrameSpec } from "@/lib/types";

interface UseCutPlan {
  stockLength: number;
  setStockLength: (v: number) => void;
  kerf: number;
  setKerf: (v: number) => void;
  result: CutPlanResponse | null;
  loading: boolean;
  error: string | null;
  calculate: () => void;
}

export function useCutPlan(spec: FrameSpec | null): UseCutPlan {
  const [stockLength, setStockLength] = useState(3000);
  const [kerf, setKerf] = useState(3);
  // Store the result together with the spec key it was computed for so we
  // can derive staleness without calling setState in an effect.
  const [resultEntry, setResultEntry] = useState<{
    specKey: string;
    data: CutPlanResponse;
  } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const currentKey = spec ? JSON.stringify(spec) : null;
  // Result is valid only when it was computed for the current spec.
  const result =
    resultEntry !== null && resultEntry.specKey === currentKey
      ? resultEntry.data
      : null;

  const calculate = useCallback(() => {
    if (!spec) return;

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    const specKey = JSON.stringify(spec);
    setLoading(true);
    setError(null);

    globalThis
      .fetch("/cut-plan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          spec,
          stock_length_mm: stockLength,
          kerf_mm: kerf,
        }),
        signal: controller.signal,
      })
      .then(async (res) => {
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          throw new Error(
            (body as { detail?: string }).detail ?? `HTTP ${res.status}`,
          );
        }
        return res.json() as Promise<CutPlanResponse>;
      })
      .then((data) => {
        setResultEntry({ specKey, data });
      })
      .catch((err: Error) => {
        if (err.name === "AbortError") return;
        setError(err.message);
      })
      .finally(() => {
        setLoading(false);
      });
  }, [spec, stockLength, kerf]);

  return {
    stockLength,
    setStockLength,
    kerf,
    setKerf,
    result,
    loading,
    error,
    calculate,
  };
}
