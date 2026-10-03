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

    const params = new URLSearchParams({
      width: String(spec.width_mm),
      depth: String(spec.depth_mm),
      height: String(spec.height_mm),
      series: spec.profile_series,
      load_kg: String(spec.target_load_kg),
    });
    if (spec.shelf_height_mm !== null && spec.shelf_height_mm !== undefined) {
      params.set("shelf", String(spec.shelf_height_mm));
    }
    if (spec.centre_legs) params.set("centre_legs", "true");

    try {
      const res = await globalThis.fetch(`/frame?${params}`, {
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
