"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import type { FrameResponse, FrameSpec } from "@/lib/types";
import { PromptBar } from "@/components/PromptBar";
import { SidePanel } from "@/components/panel/SidePanel";
import { EmptyState } from "@/components/EmptyState";
import { ThemeToggle } from "@/components/ThemeToggle";
import { useFrameApi } from "@/hooks/useFrameApi";
import { useParseApi } from "@/hooks/useParseApi";
import { useSuggestApi } from "@/hooks/useSuggestApi";
import { useUndo } from "@/hooks/useUndo";

// Three.js must not run on the server — load the canvas client-side only.
// No `loading` fallback here: FrameViewerCanvas handles it with its own Suspense.
const FrameViewerCanvas = dynamic(
  () =>
    import("@/components/viewer/FrameViewer").then((m) => m.FrameViewerCanvas),
  { ssr: false }
);

export function FrameDesigner() {
  const [promptText, setPromptText]         = useState("");
  const [parseError, setParseError]         = useState<string | null>(null);
  const [spec, setSpec]                     = useState<FrameSpec | null>(null);
  const [frameData, setFrameData]           = useState<FrameResponse | null>(null);
  const [highlightLength, setHighlightLength] = useState<number | null>(null);
  const [frameKey, setFrameKey]             = useState(0);

  const frameIdRef   = useRef(0);
  const lastPromptRef = useRef("");

  const { loading: parsing,    parse }      = useParseApi();
  const { loading: generating, error: frameError, fetch: fetchFrame } = useFrameApi();
  const { suggest, setFrameId }             = useSuggestApi();
  const undo                                = useUndo();

  const loading = parsing || generating;

  // ── Generate ───────────────────────────────────────────────────────────────

  const generate = useCallback(
    async (nextSpec: FrameSpec) => {
      setSpec(nextSpec);
      setHighlightLength(null);

      const frameId = ++frameIdRef.current;
      setFrameId(frameId);
      setFrameKey(frameId); // triggers bar remount → replays animation

      const data = await fetchFrame(nextSpec);
      if (!data) return;

      setFrameData(data);

      if (data.suggestions.length > 0 && lastPromptRef.current) {
        void suggest(
          nextSpec,
          lastPromptRef.current,
          frameId,
          (ranked) =>
            setFrameData((prev) =>
              prev ? { ...prev, suggestions: ranked } : prev
            )
        );
      }
    },
    [fetchFrame, suggest, setFrameId]
  );

  // ── Prompt parsing ─────────────────────────────────────────────────────────

  const submitPrompt = useCallback(
    async (text: string) => {
      setParseError(null);
      lastPromptRef.current = text;

      const result = await parse(text);
      if (!result) return;

      if (result.outcome === "spec_valid" && result.spec) {
        void generate(result.spec);
      } else {
        setParseError(
          result.error ?? "Could not understand the request. Try rewording it."
        );
      }
    },
    [parse, generate]
  );

  function handlePromptSubmit() {
    const t = promptText.trim();
    if (t) void submitPrompt(t);
  }

  function handleExampleSelect(prompt: string) {
    setPromptText(prompt);
    void submitPrompt(prompt);
  }

  // ── Undo (button + Ctrl/Cmd+Z) ─────────────────────────────────────────────

  const handleUndo = useCallback(() => {
    const prev = undo.take();
    if (prev) void generate(prev);
  }, [undo, generate]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key === "z" && !e.shiftKey) {
        e.preventDefault();
        handleUndo();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [handleUndo]);

  // ── Derived values ─────────────────────────────────────────────────────────

  const dims = spec
    ? { widthMm: spec.width_mm, depthMm: spec.depth_mm, heightMm: spec.height_mm }
    : undefined;

  const error = parseError ?? frameError;

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className="flex flex-col h-full">
      {/* Top bar */}
      <header className="shrink-0 border-b border-border bg-surface px-4 py-3 flex items-start gap-2">
        <div className="flex-1 min-w-0">
          <PromptBar
            value={promptText}
            onChange={setPromptText}
            onSubmit={handlePromptSubmit}
            loading={loading}
            error={error}
            onDismissError={() => setParseError(null)}
          />
        </div>
        <ThemeToggle />
      </header>

      {/* Main — stacked on mobile, side-by-side on desktop */}
      <div className="flex flex-col md:flex-row flex-1 min-h-0">
        {/* Viewer / empty state */}
        <main className="flex-1 min-w-0 min-h-48 md:min-h-0 p-3">
          {frameData ? (
            <div
              className="h-full w-full rounded-lg overflow-hidden"
              style={{ background: "var(--bg)" }}
            >
              <FrameViewerCanvas
                bars={frameData.bars}
                dims={dims}
                highlightLength={highlightLength}
                frameKey={frameKey}
              />
            </div>
          ) : (
            <EmptyState onSelect={handleExampleSelect} />
          )}
        </main>

        {/* Side panel */}
        <SidePanel
          spec={spec}
          frameData={frameData}
          loading={loading}
          canUndo={undo.canUndo}
          onGenerate={(s) => void generate(s)}
          onApply={(c) => { if (spec) undo.save(spec); void generate(c.spec); }}
          onUndo={handleUndo}
          onCutListRowHover={setHighlightLength}
        />
      </div>
    </div>
  );
}
