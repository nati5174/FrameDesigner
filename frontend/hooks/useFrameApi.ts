"use client";

import { useCallback, useRef, useState } from "react";
import type { FrameResponse, FrameSpec } from "@/lib/types";

interface UseFrameApi {
  data: FrameResponse | null;
  loading: boolean;
  error: string | null;
  fetch: (spec: FrameSpec) => Promise<FrameResponse | null>;
}

export function useFrameApi(): UseFrameApi {
  const [data, setData] = useState<FrameResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const fetch = useCallback(async (spec: FrameSpec): Promise<FrameResponse | null> => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    setError(null);

    try {
      const res = await globalThis.fetch("/frame", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ spec }),
        signal: controller.signal,
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error((body as { detail?: string }).detail ?? `HTTP ${res.status}`);
      }
      const json: FrameResponse = await res.json();
      setData(json);
      return json;
    } catch (err) {
      if ((err as Error).name === "AbortError") return null;
      const msg = (err as Error).message;
      setError(msg);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  return { data, loading, error, fetch };
}
