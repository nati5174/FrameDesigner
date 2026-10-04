"use client";

import { useCallback, useRef, useState } from "react";
import dynamic from "next/dynamic";
import type { AssistantCard, FixCandidate, FrameResponse, FrameSpec } from "@/lib/types";
import { PromptBar } from "@/components/PromptBar";
import { SidePanel } from "@/components/panel/SidePanel";
import { EmptyState } from "@/components/EmptyState";
import { ThemeToggle } from "@/components/ThemeToggle";
import { ConversationThread } from "@/components/thread/ConversationThread";
import { useFrameApi } from "@/hooks/useFrameApi";
import { useEditApi } from "@/hooks/useEditApi";
import { useThread } from "@/hooks/useThread";
import { useSuggestApi } from "@/hooks/useSuggestApi";

const FrameViewerCanvas = dynamic(
  () =>
    import("@/components/viewer/FrameViewer").then((m) => m.FrameViewerCanvas),
  { ssr: false }
);

export function FrameDesigner() {
  const [promptText, setPromptText]           = useState("");
  const [highlightLength, setHighlightLength] = useState<number | null>(null);
  const [frameKey, setFrameKey]               = useState(0);
  const [frameData, setFrameData]             = useState<FrameResponse | null>(null);

  const frameIdRef    = useRef(0);
  const lastPromptRef = useRef("");

  const { loading: editing,    edit }       = useEditApi();
  const { loading: generating, error: frameError, fetch: fetchFrame } = useFrameApi();
  const { suggest, setFrameId }             = useSuggestApi();
  const thread                              = useThread();

  const loading = editing || generating;

  // ── Generate frame from spec ───────────────────────────────────────────────

  const generate = useCallback(
    async (spec: FrameSpec): Promise<FrameResponse | null> => {
      setHighlightLength(null);
      const frameId = ++frameIdRef.current;
      setFrameId(frameId);
      setFrameKey(frameId);

      const data = await fetchFrame(spec);
      if (!data) return null;

      setFrameData(data);

      if (data.suggestions.length > 0 && lastPromptRef.current) {
        void suggest(
          spec,
          lastPromptRef.current,
          frameId,
          (ranked) =>
            setFrameData((prev) =>
              prev ? { ...prev, suggestions: ranked } : prev
            )
        );
      }
      return data;
    },
    [fetchFrame, suggest, setFrameId]
  );

  // ── Submit prompt ──────────────────────────────────────────────────────────

  const submitPrompt = useCallback(
    async (text: string) => {
      lastPromptRef.current = text;
      thread.addUserEntry(text);
      thread.addLoadingEntry();

      let editResp;
      try {
        editResp = await edit({
          text,
          spec: thread.currentSpec,
          pending: thread.pending,
        });
      } catch {
        thread.resolveLastEntry(
          { type: "error", message: "Network error — please try again." },
          null,
          null
        );
        return;
      }
      if (!editResp) return;

      const { outcome, spec, changes, defaults_applied, error } = editResp;

      if (outcome === "new_design" || outcome === "edit") {
        if (!spec) {
          thread.resolveLastEntry(
            { type: "error", message: error ?? "Unexpected empty spec." },
            null,
            null
          );
          return;
        }
        const data = await generate(spec);
        const card: AssistantCard =
          outcome === "new_design"
            ? { type: "new_design", spec, changes, defaults: defaults_applied, frameData: data }
            : { type: "edit", spec, changes, frameData: data };
        thread.resolveLastEntry(card, spec, null);
        return;
      }

      if (outcome === "clarify") {
        thread.resolveLastEntry(
          { type: "clarify", pending: editResp.pending ?? {}, missing: editResp.missing },
          null,
          editResp.pending
        );
        return;
      }

      if (outcome === "unsupported") {
        thread.resolveLastEntry(
          { type: "unsupported", message: error ?? "This request is not supported." },
          null,
          null
        );
        return;
      }

      thread.resolveLastEntry(
        {
          type: "error",
          message: error ?? "Could not understand the request. Try rewording it.",
        },
        null,
        null
      );
    },
    [edit, generate, thread]
  );

  function handlePromptSubmit() {
    const t = promptText.trim();
    if (t) void submitPrompt(t);
  }

  function handleExampleSelect(prompt: string) {
    setPromptText(prompt);
    void submitPrompt(prompt);
  }

  const handleRestore = useCallback(
    async (spec: FrameSpec) => {
      thread.restoreToSpec(spec);
      await generate(spec);
    },
    [thread, generate]
  );

  const handleApply = useCallback(
    async (candidate: FixCandidate) => {
      await generate(candidate.spec);
    },
    [generate]
  );

  // ── Derived values ─────────────────────────────────────────────────────────

  const spec = thread.currentSpec;
  const dims = spec
    ? { widthMm: spec.width_mm, depthMm: spec.depth_mm, heightMm: spec.height_mm }
    : undefined;

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
            error={frameError}
            onDismissError={() => {}}
          />
        </div>
        <ThemeToggle />
      </header>

      {/* Conversation thread */}
      {thread.entries.length > 0 && (
        <div className="shrink-0 max-h-48 overflow-y-auto border-b border-border bg-background">
          <ConversationThread
            entries={thread.entries}
            onRestoreSpec={handleRestore}
            onChip={(text) => void submitPrompt(text)}
          />
        </div>
      )}

      {/* Main */}
      <div className="flex flex-col md:flex-row flex-1 min-h-0">
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

        <SidePanel
          spec={spec}
          frameData={frameData}
          loading={loading}
          canUndo={false}
          onGenerate={(s) => void generate(s)}
          onApply={handleApply}
          onUndo={() => {}}
          onCutListRowHover={setHighlightLength}
        />
      </div>
    </div>
  );
}
