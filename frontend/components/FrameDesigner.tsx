"use client";

import { useCallback, useRef, useState } from "react";
import dynamic from "next/dynamic";
import type { FixCandidate, FrameResponse, FrameSpec } from "@/lib/types";
import { PromptBar } from "@/components/PromptBar";
import { SidePanel } from "@/components/panel/SidePanel";
import { FrameViewerPlaceholder } from "@/components/viewer/FrameViewerPlaceholder";
import { useFrameApi } from "@/hooks/useFrameApi";
import { useParseApi } from "@/hooks/useParseApi";
import { useSuggestApi } from "@/hooks/useSuggestApi";
import { useUndo } from "@/hooks/useUndo";

// Three.js must not run on the server — load the canvas client-side only.
const FrameViewerCanvas = dynamic(
  () => import("@/components/viewer/FrameViewer").then((m) => m.FrameViewerCanvas),
  { ssr: false, loading: () => <FrameViewerPlaceholder hasFrame={false} /> }
);

export function FrameDesigner() {
  const [promptText, setPromptText] = useState("");
  const [parseError, setParseError] = useState<string | null>(null);
  const [spec, setSpec] = useState<FrameSpec | null>(null);
  const [frameData, setFrameData] = useState<FrameResponse | null>(null);
  const [highlightLength, setHighlightLength] = useState<number | null>(null);

  const frameIdRef = useRef(0);
  const lastPromptRef = useRef("");

  const { loading: parsing, parse } = useParseApi();
  const { loading: generating, error: frameError, fetch: fetchFrame } = useFrameApi();
  const { suggest, setFrameId } = useSuggestApi();
  const undo = useUndo();

  const loading = parsing || generating;

  const generate = useCallback(
    async (nextSpec: FrameSpec) => {
      setSpec(nextSpec);
      setHighlightLength(null);

      const frameId = ++frameIdRef.current;
      setFrameId(frameId);

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

  async function submitPrompt(text: string) {
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
  }

  function handlePromptSubmit() {
    const trimmed = promptText.trim();
    if (trimmed) void submitPrompt(trimmed);
  }

  function handleExampleSelect(prompt: string) {
    setPromptText(prompt);
    void submitPrompt(prompt);
  }

  function handleGenerate(nextSpec: FrameSpec) {
    void generate(nextSpec);
  }

  function handleApply(candidate: FixCandidate) {
    if (spec) undo.save(spec);
    void generate(candidate.spec);
  }

  function handleUndo() {
    const prev = undo.take();
    if (prev) void generate(prev);
  }

  const dims = spec
    ? { widthMm: spec.width_mm, depthMm: spec.depth_mm, heightMm: spec.height_mm }
    : undefined;

  const error = parseError ?? frameError;

  return (
    <div className="flex flex-col h-full">
      <header className="shrink-0 border-b border-border bg-surface px-4 py-3">
        <PromptBar
          value={promptText}
          onChange={setPromptText}
          onSubmit={handlePromptSubmit}
          loading={loading}
          error={error}
          onDismissError={() => setParseError(null)}
        />
      </header>

      <div className="flex flex-1 min-h-0 relative">
        <main className="flex-1 min-w-0 p-4">
          {frameData ? (
            <FrameViewerCanvas
              bars={frameData.bars}
              dims={dims}
              highlightLength={highlightLength}
            />
          ) : (
            <FrameViewerPlaceholder hasFrame={false} />
          )}
        </main>

        <SidePanel
          spec={spec}
          frameData={frameData}
          loading={loading}
          canUndo={undo.canUndo}
          onGenerate={handleGenerate}
          onApply={handleApply}
          onUndo={handleUndo}
          onExampleSelect={handleExampleSelect}
          onCutListRowHover={setHighlightLength}
        />
      </div>
    </div>
  );
}
