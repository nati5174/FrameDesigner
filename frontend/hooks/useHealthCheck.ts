"use client";

import { useEffect, useState } from "react";

const POLL_INTERVAL_MS = 3000;

/**
 * Polls GET /health on mount, retrying every `pollMs` milliseconds on any
 * failure (network error, non-2xx status, or timeout).  Returns true once
 * the server responds with a 2xx status, false until then.
 *
 * `pollMs` is configurable so tests can pass 0 to avoid fake timers.
 * Production code uses the default 3 000 ms interval.
 *
 * Used to show a cold-start message while a Render free dyno wakes up.
 */
export function useHealthCheck(pollMs = POLL_INTERVAL_MS): boolean {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function poll(): Promise<void> {
      while (!cancelled) {
        try {
          const res = await globalThis.fetch("/health");
          if (res.ok && !cancelled) {
            setReady(true);
            return;
          }
        } catch {
          // network error or timeout — fall through to retry
        }
        if (!cancelled) {
          await new Promise<void>((resolve) =>
            setTimeout(resolve, pollMs)
          );
        }
      }
    }

    void poll();
    return () => {
      cancelled = true;
    };
  }, []);

  return ready;
}
