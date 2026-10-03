"use client";

import { useCallback, useRef, useState } from "react";
import type { ParseResponse } from "@/lib/types";

interface UseParseApi {
  result: ParseResponse | null;
  loading: boolean;
  error: string | null;
  parse: (text: string) => Promise<ParseResponse | null>;
}

export function useParseApi(): UseParseApi {
  const [result, setResult] = useState<ParseResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const parse = useCallback(async (text: string): Promise<ParseResponse | null> => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    setError(null);

    try {
      const res = await fetch("/parse", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
        signal: controller.signal,
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error((body as { detail?: string }).detail ?? `HTTP ${res.status}`);
      }
      const json: ParseResponse = await res.json();
      setResult(json);
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

  return { result, loading, error, parse };
}
