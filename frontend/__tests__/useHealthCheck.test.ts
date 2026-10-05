import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useHealthCheck } from "@/hooks/useHealthCheck";

// All tests pass pollMs=0 so no real or fake timer delay is needed.

describe("useHealthCheck", () => {
  beforeEach(() => {
    vi.spyOn(globalThis, "fetch");
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns false before /health responds", () => {
    // Promise that never resolves during this synchronous tick
    vi.mocked(globalThis.fetch).mockImplementation(
      () => new Promise<Response>(() => {})
    );
    const { result } = renderHook(() => useHealthCheck(0));
    expect(result.current).toBe(false);
  });

  it("returns true after a successful /health response", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue({ ok: true } as Response);
    const { result } = renderHook(() => useHealthCheck(0));
    await waitFor(() => expect(result.current).toBe(true));
  });

  it("stays false on a 502 response and retries until success", async () => {
    vi.mocked(globalThis.fetch)
      .mockResolvedValueOnce({ ok: false, status: 502 } as Response)
      .mockResolvedValue({ ok: true } as Response);

    const { result } = renderHook(() => useHealthCheck(0));
    await waitFor(() => expect(result.current).toBe(true));
  });

  it("stays false on a network error and retries until success", async () => {
    vi.mocked(globalThis.fetch)
      .mockRejectedValueOnce(new TypeError("Failed to fetch"))
      .mockResolvedValue({ ok: true } as Response);

    const { result } = renderHook(() => useHealthCheck(0));
    await waitFor(() => expect(result.current).toBe(true));
  });
});
