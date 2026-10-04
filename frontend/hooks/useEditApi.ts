"use client";

import { useCallback, useRef, useState } from "react";
import type { EditRequest, EditResponse } from "@/lib/types";

export interface UseEditApi {
  loading: boolean;
  edit: (req: EditRequest) => Promise<EditResponse | null>;
}

export function useEditApi(): UseEditApi {
  const [loading, setLoading] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const edit = useCallback(async (req: EditRequest): Promise<EditResponse | null> => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setLoading(true);
    try {
      const res = await fetch("/edit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(req),
        signal: controller.signal,
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(
          (body as { detail?: string }).detail ?? `HTTP ${res.status}`
        );
      }
      return (await res.json()) as EditResponse;
    } catch (err) {
      if ((err as Error).name === "AbortError") return null;
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  return { loading, edit };
}
