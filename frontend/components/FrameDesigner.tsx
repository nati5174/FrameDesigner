"use client";

import { useCallback, useRef, useState } from "react";
import dynamic from "next/dynamic";
import type { AssistantCard, FieldChange, FixCandidate, FrameResponse, FrameSpec } from "@/lib/types";
import { PromptBar } from "@/components/PromptBar";
import { SidePanel } from "@/components/panel/SidePanel";
import { EmptyState } from "@/components/EmptyState";
import { ThemeToggle } from "@/components/ThemeToggle";
import { ConversationThread } from "@/components/thread/ConversationThread";
import { ThreadSheet } from "@/components/thread/ThreadSheet";
import { DetailsSheet } from "@/components/panel/DetailsSheet";
import { useFrameApi } from "@/hooks/useFrameApi";
import { useEditApi } from "@/hooks/useEditApi";
import { useThread } from "@/hooks/useThread";
import { useSuggestApi } from "@/hooks/useSuggestApi";

// ── Helpers for form-edit thread entries ──────────────────────────────────────

function buildChanges(oldSpec: FrameSpec, newSpec: FrameSpec): FieldChange[] {
  const keys: (keyof FrameSpec)[] = [
    "frame_type", "width_mm", "depth_mm", "height_mm",
    "shelf_height_mm", "target_load_kg", "centre_legs",
    "level_heights_mm", "load_per_level_kg",
  ];
  return keys
    .filter((k) => JSON.stringify(oldSpec[k]) !== JSON.stringify(newSpec[k]))
    .map((k) => ({ field: k, old: oldSpec[k] as FieldChange["old"], new: newSpec[k] as FieldChange["new"] }));
}

function fieldLabel(raw: string): string {
  return raw.replace(/_mm$|_kg$/, "").replace(/_/g, " ");
}

function formEditText(changes: FieldChange[]): string {
  if (changes.length === 0) return "Form edit";
  if (changes.length === 1) return `Set ${fieldLabel(changes[0].field)} to ${changes[0].new}`;
  return `Changed ${changes.length} fields via form`;
}

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

  const handleFormEdit = useCallback(
    async (newSpec: FrameSpec) => {
      const oldSpec = thread.currentSpec;
      const changes = oldSpec ? buildChanges(oldSpec, newSpec) : [];
      thread.addUserEntry(formEditText(changes));
      thread.addLoadingEntry();
      const data = await generate(newSpec);
      const card: AssistantCard = { type: "edit", spec: newSpec, changes, frameData: data };
      thread.resolveLastEntry(card, newSpec, null);
    },
    [generate, thread]
  );

  const handleNewDesign = useCallback(() => {
    thread.clear();
    setFrameData(null);
  }, [thread]);

  // ── Derived values ─────────────────────────────────────────────────────────

  const spec = thread.currentSpec;
  const dims = spec
    ? { widthMm: spec.width_mm, depthMm: spec.depth_mm, heightMm: spec.height_mm }
    : undefined;

  // ── Render ─────────────────────────────────────────────────────────────────

  const hasThread = thread.entries.length > 0;
  const threadProps = {
    entries: thread.entries,
    onRestoreSpec: handleRestore,
    onChip: (text: string) => void submitPrompt(text),
  };

  return (
    <div className="flex flex-col h-full overflow-x-hidden">
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
        {hasThread && (
          <button
            type="button"
            onClick={handleNewDesign}
            className="shrink-0 rounded-md border border-border px-3 py-1.5 text-xs text-muted hover:text-foreground hover:border-foreground transition-colors"
          >
            New design
          </button>
        )}
        <ThemeToggle />
      </header>

      {/* Main content area */}
      <div className="flex flex-1 min-h-0">
        {/* Desktop thread column (hidden on mobile) */}
        {hasThread && (
          <aside className="hidden md:flex flex-col w-72 shrink-0 border-r border-border bg-background overflow-y-auto">
            <ConversationThread {...threadProps} />
          </aside>
        )}

        {/* Viewer + side panel */}
        <div className="flex flex-col md:flex-row flex-1 min-h-0 min-w-0">
          {/* Viewer — on mobile add bottom padding to clear the ThreadSheet handle */}
          <main className="flex-1 min-w-0 min-h-48 md:min-h-0 p-3 pb-14 md:pb-3">
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

          {/* Desktop side panel only — DetailsSheet handles mobile */}
          <div className="hidden md:contents">
            <SidePanel
              spec={spec}
              frameData={frameData}
              loading={loading}
              canUndo={false}
              onGenerate={(s) => void handleFormEdit(s)}
              onApply={handleApply}
              onUndo={() => {}}
              onCutListRowHover={setHighlightLength}
            />
          </div>
        </div>
      </div>

      {/* Mobile-only sheets */}
      <div className="md:hidden">
        <DetailsSheet
          spec={spec}
          frameData={frameData}
          loading={loading}
          canUndo={false}
          onGenerate={(s) => void handleFormEdit(s)}
          onApply={handleApply}
          onUndo={() => {}}
          onCutListRowHover={setHighlightLength}
        />
        <ThreadSheet
          entries={thread.entries}
          onRestoreSpec={handleRestore}
          onChip={(text) => void submitPrompt(text)}
        />
      </div>
    </div>
  );
}
