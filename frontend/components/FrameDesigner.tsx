"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import type {
  AssistantCard,
  CheckReport,
  FieldChange,
  FixCandidate,
  FrameResponse,
  FrameSpec,
} from "@/lib/types";
import { PromptBar } from "@/components/PromptBar";
import { SidePanel } from "@/components/panel/SidePanel";
import { EmptyState } from "@/components/EmptyState";
import { ThemeToggle } from "@/components/ThemeToggle";
import { ConversationThread } from "@/components/thread/ConversationThread";
import { ThreadSheet } from "@/components/thread/ThreadSheet";
import { DetailsSheet } from "@/components/panel/DetailsSheet";
import { CollapsibleSection } from "@/components/panel/CollapsibleSection";
import { CutList } from "@/components/panel/CutList";
import { CutPlan } from "@/components/panel/CutPlan";
import { DimensionsForm } from "@/components/panel/DimensionsForm";
import { LoadCheck } from "@/components/panel/LoadCheck";
import { PartsList } from "@/components/panel/PartsList";
import { StatusBadge } from "@/components/StatusBadge";
import { SuggestionCard } from "@/components/panel/SuggestionCard";
import { useFrameApi } from "@/hooks/useFrameApi";
import { useEditApi } from "@/hooks/useEditApi";
import { useHealthCheck } from "@/hooks/useHealthCheck";
import { useThread } from "@/hooks/useThread";
import { useSuggestApi } from "@/hooks/useSuggestApi";
import { DEFAULT_SPEC, EXAMPLES } from "@/lib/examples";
import { formatRole, usd } from "@/lib/labels";

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

function fieldUnit(key: string): string {
  if (key.endsWith("_mm")) return " mm";
  if (key.endsWith("_kg")) return " kg";
  return "";
}

function formEditText(changes: FieldChange[], newSpec: FrameSpec): string {
  if (changes.length === 0) {
    return `${newSpec.width_mm} × ${newSpec.depth_mm} × ${newSpec.height_mm} mm`;
  }
  if (changes.length === 1) {
    const c = changes[0];
    return `Set ${fieldLabel(c.field)} to ${c.new}${fieldUnit(c.field)}`;
  }
  return `Changed ${changes.length} fields via form`;
}

// ── Bottom strip ──────────────────────────────────────────────────────────────

function BottomStrip({ report }: { report: CheckReport }) {
  const gov = report.load.governing_rail;
  if (!gov) return null;

  const cells = [
    { label: "Governing rail", value: `${formatRole(gov.role)} · ${gov.span_mm} mm` },
    {
      label: "Stress",
      value: `${gov.distributed.bending_stress_mpa.toFixed(2)} / ${gov.allowable_stress_mpa.toFixed(2)} MPa`,
    },
    {
      label: "Deflection",
      value: `${gov.distributed.deflection_mm.toFixed(2)} / ${gov.deflection_limit_mm.toFixed(2)} mm`,
    },
    { label: "Utilisation", value: `${(gov.utilisation * 100).toFixed(0)} %` },
  ];

  return (
    <div className="grid grid-cols-4 border-t border-border shrink-0">
      {cells.map((c, i) => (
        <div
          key={c.label}
          className={`px-3 py-2 bg-surface/90 ${i < 3 ? "border-r border-border" : ""}`}
        >
          <p className="text-[10px] font-mono text-muted tracking-[0.06em] uppercase leading-none">
            {c.label}
          </p>
          <p className="text-sm font-mono text-text mt-1 leading-none">{c.value}</p>
        </div>
      ))}
    </div>
  );
}

// ── Right panel tabs ──────────────────────────────────────────────────────────

type RightTab = "parts" | "cut-plan" | "load-check";

interface RightPanelProps {
  spec: FrameSpec | null;
  frameData: FrameResponse;
  canUndo: boolean;
  activeTab: RightTab;
  onTabChange: (tab: RightTab) => void;
  onApply: (candidate: FixCandidate) => void;
  onUndo: () => void;
  onCutListRowHover?: (lengthMm: number | null) => void;
}

const TABS: { id: RightTab; label: string }[] = [
  { id: "parts", label: "Parts" },
  { id: "cut-plan", label: "Cut plan" },
  { id: "load-check", label: "Load check" },
];

function RightPanel({
  spec,
  frameData,
  canUndo,
  activeTab,
  onTabChange,
  onApply,
  onUndo,
  onCutListRowHover,
}: RightPanelProps) {
  const totalCost = frameData.total_cost_usd ?? null;

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Total to order */}
      <div className="shrink-0 border-b border-border px-4 py-3">
        <p className="text-[10px] font-mono text-muted tracking-[0.12em] uppercase">
          Total to order
        </p>
        <p className="text-2xl font-mono font-medium text-text mt-1 leading-none">
          {totalCost != null ? `$${usd(totalCost)}` : "—"}
        </p>
        {totalCost != null && (
          <div className="flex gap-3 mt-1 text-[11px] font-mono text-muted">
            {frameData.cut_list_total_cost_usd != null && (
              <span>Bars ${usd(frameData.cut_list_total_cost_usd)}</span>
            )}
            {frameData.hardware_cost_usd != null && (
              <span>Hardware ${usd(frameData.hardware_cost_usd)}</span>
            )}
          </div>
        )}
        {/* Cost saving — one inline line when present */}
        {frameData.cost_suggestion && (
          <p className="mt-1.5 text-[11px] font-mono text-muted">
            Switch to {frameData.cost_suggestion.spec.profile_series} →{" "}
            <button
              type="button"
              onClick={() => onApply(frameData.cost_suggestion!)}
              className="text-text underline decoration-dotted hover:text-ink transition-colors"
            >
              Apply
            </button>
          </p>
        )}
        {/* Status badge — full row so it never clips */}
        <div className="mt-2">
          <StatusBadge checkReport={frameData.check_report} />
        </div>
      </div>

      {/* Tabs */}
      <div className="shrink-0 border-b border-border flex">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => onTabChange(t.id)}
            className={`
              flex-1 py-2 text-xs font-medium transition-colors
              ${activeTab === t.id
                ? "text-accent border-b-[3px] border-accent -mb-px"
                : "text-muted hover:text-text border-b-[3px] border-transparent -mb-px"
              }
            `}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="flex-1 min-h-0 overflow-y-auto">
        {activeTab === "parts" && (
          <div className="px-4 py-4 flex flex-col gap-6">
            <CutList
              rows={frameData.cut_list}
              totalCostUsd={frameData.cut_list_total_cost_usd}
              totalWeightKg={frameData.cut_list_total_weight_kg}
              onRowHover={onCutListRowHover}
              spec={spec}
            />
            <PartsList
              rows={frameData.parts_list ?? []}
              hardwareCostUsd={frameData.hardware_cost_usd ?? null}
              hardwareWeightKg={frameData.hardware_weight_kg ?? null}
              barsCostUsd={frameData.cut_list_total_cost_usd}
              barsWeightKg={frameData.cut_list_total_weight_kg}
              totalCostUsd={frameData.total_cost_usd ?? null}
              totalWeightKg={frameData.total_weight_kg ?? null}
              hardwarePriced={frameData.hardware_priced ?? false}
              spec={spec}
              cutListRows={frameData.cut_list}
            />
          </div>
        )}

        {activeTab === "cut-plan" && spec && (
          <div className="px-4 py-4">
            <CutPlan spec={spec} />
          </div>
        )}
        {activeTab === "cut-plan" && !spec && (
          <p className="px-4 py-4 text-sm text-muted">No spec loaded.</p>
        )}

        {activeTab === "load-check" && (
          <div className="px-4 py-4">
            <LoadCheck checkReport={frameData.check_report} />
          </div>
        )}
      </div>
    </div>
  );
}

// ── Viewer ────────────────────────────────────────────────────────────────────

const FrameViewerCanvas = dynamic(
  () =>
    import("@/components/viewer/FrameViewer").then((m) => m.FrameViewerCanvas),
  { ssr: false }
);

// ── Main component ────────────────────────────────────────────────────────────

export function FrameDesigner() {
  const serverReady = useHealthCheck();

  const [promptText, setPromptText]           = useState("");
  const [highlightLength, setHighlightLength] = useState<number | null>(null);
  const [frameKey, setFrameKey]               = useState(0);
  const [frameData, setFrameData]             = useState<FrameResponse | null>(null);
  const [rightTab, setRightTab]               = useState<RightTab>("parts");
  const [dimsOpen, setDimsOpen]               = useState(false);
  // JS-based layout switch so only ONE PromptBar exists in the DOM at a time.
  // Starts false (mobile) to match server render, updated after mount.
  const [isDesktop, setIsDesktop]             = useState(false);

  const frameIdRef    = useRef(0);
  const lastPromptRef = useRef("");
  const autoLoadedRef = useRef(false);

  const { loading: editing,    edit }       = useEditApi();
  const { loading: generating, error: frameError, fetch: fetchFrame } = useFrameApi();
  const { suggest, setFrameId }             = useSuggestApi();
  const thread                              = useThread();

  const loading = editing || generating;

  // ── Desktop breakpoint detection ───────────────────────────────────────────

  useEffect(() => {
    const check = () => setIsDesktop(window.innerWidth >= 1280);
    check();
    window.addEventListener("resize", check);
    return () => window.removeEventListener("resize", check);
  }, []);

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

  // ── Auto-load default design on first visit ────────────────────────────────

  const { addLoadingEntry, resolveLastEntry } = thread;

  useEffect(() => {
    if (!serverReady) return;
    if (!thread.hydrated) return;
    if (thread.entries.length > 0 || thread.currentSpec) return;
    if (autoLoadedRef.current) return;
    autoLoadedRef.current = true;

    addLoadingEntry();
    void (async () => {
      const data = await generate(DEFAULT_SPEC);
      const card: AssistantCard = {
        type: "example",
        spec: DEFAULT_SPEC,
        message:
          "Here is an example to start from: workbench 1500 × 700 × 900 mm, 100 kg",
        frameData: data,
      };
      resolveLastEntry(card, DEFAULT_SPEC, null);
    })();
  }, [
    serverReady,
    thread.hydrated,
    thread.entries.length,
    thread.currentSpec,
    generate,
    addLoadingEntry,
    resolveLastEntry,
  ]);

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
    if (t) {
      setPromptText("");
      void submitPrompt(t);
    }
  }

  function handleExampleSelect(prompt: string) {
    setPromptText("");
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
      thread.addUserEntry(formEditText(changes, newSpec));
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

  const hasThread = thread.entries.length > 0;
  const isExampleState = hasThread && thread.entries.every((e) => e.role === "assistant");

  const threadProps = {
    entries: thread.entries,
    onRestoreSpec: handleRestore,
    onChip: (text: string) => void submitPrompt(text),
  };

  // ── Cold-start screen ──────────────────────────────────────────────────────

  if (!serverReady) {
    return (
      <div className="flex h-full items-center justify-center p-8">
        <p className="text-sm text-center" style={{ color: "var(--muted)" }}>
          Starting the server, this can take up to a minute…
        </p>
      </div>
    );
  }

  // ── Render ─────────────────────────────────────────────────────────────────

  if (isDesktop) {
    return (
      <div className="flex h-full overflow-hidden">

        {/* LEFT column — thread + input */}
        <aside
          className="w-[340px] shrink-0 flex flex-col bg-surface overflow-hidden"
          style={{ borderRight: "1px solid var(--rule)" }}
        >
          {/* Header strip */}
          <div
            className="shrink-0 flex items-center justify-between px-4 py-3"
            style={{ borderBottom: "1px solid var(--rule)" }}
          >
            <span className="text-[10px] font-mono text-muted tracking-[0.12em] uppercase">
              Frame Designer
            </span>
            <div className="flex items-center gap-1">
              {hasThread && (
                <button
                  type="button"
                  onClick={handleNewDesign}
                  className="rounded border border-border px-2.5 py-1 text-xs text-muted hover:text-text hover:border-text transition-colors"
                >
                  New design
                </button>
              )}
              <ThemeToggle />
            </div>
          </div>

          {/* Dimensions form — collapsible, only when spec present */}
          {spec && (
            <div
              className="shrink-0"
              style={{ borderBottom: "1px solid var(--rule)" }}
            >
              <button
                type="button"
                onClick={() => setDimsOpen((v) => !v)}
                className="w-full flex items-center justify-between px-4 py-2.5 text-[10px] font-mono text-muted tracking-[0.12em] uppercase hover:text-text transition-colors"
              >
                <span>Dimensions</span>
                <span>{dimsOpen ? "▲" : "▼"}</span>
              </button>
              {dimsOpen && (
                <div className="px-4 pb-4">
                  <DimensionsForm
                    spec={spec}
                    loading={loading}
                    onGenerate={(s) => void handleFormEdit(s)}
                  />
                </div>
              )}
            </div>
          )}

          {/* Thread — scrollable, takes remaining height */}
          <div className="flex-1 min-h-0 overflow-y-auto">
            {hasThread ? (
              <>
                <ConversationThread {...threadProps} />
                {isExampleState && (
                  <div className="px-4 pb-4 flex flex-col gap-3">
                    <p className="text-sm text-muted leading-relaxed">
                      Describe a frame. Get a 3D model, cut list, cost and load estimate.
                    </p>
                    <div className="flex flex-col gap-1.5">
                      <p className="text-xs text-muted">Try an example</p>
                      <div className="flex flex-wrap gap-2">
                        {EXAMPLES.map((ex) => (
                          <button
                            key={ex.prompt}
                            type="button"
                            onClick={() => handleExampleSelect(ex.prompt)}
                            className="px-3 py-1.5 border border-border bg-surface text-sm text-muted hover:border-ink hover:text-text transition-colors"
                          >
                            {ex.label}
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </>
            ) : (
              <EmptyState onSelect={handleExampleSelect} />
            )}
          </div>

          {/* Input — pinned at bottom */}
          <div
            className="shrink-0 px-3 py-3"
            style={{ borderTop: "1px solid var(--rule)" }}
          >
            <p className="text-[10px] font-mono text-muted tracking-[0.12em] uppercase mb-2">
              Change or describe
            </p>
            <PromptBar
              value={promptText}
              onChange={setPromptText}
              onSubmit={handlePromptSubmit}
              loading={loading}
              error={frameError}
              onDismissError={() => {}}
            />
          </div>
        </aside>

        {/* CENTER column — viewer + bottom strip */}
        <div
          className="flex-1 min-w-0 flex flex-col overflow-hidden"
          style={{
            background: "var(--paper)",
            backgroundImage:
              "linear-gradient(var(--grid) 1px, transparent 1px), linear-gradient(90deg, var(--grid) 1px, transparent 1px)",
            backgroundSize: "32px 32px",
          }}
        >
          {/* Caption strip */}
          <div
            className="shrink-0 px-4 py-2 text-[11px] font-mono text-muted"
            style={{ borderBottom: "1px solid var(--rule)", background: "var(--surface)" }}
          >
            {spec
              ? `${spec.width_mm} × ${spec.depth_mm} × ${spec.height_mm} mm · ${spec.profile_series ?? "40-series"}`
              : "No design loaded"}
          </div>

          {/* Viewer */}
          <div className="flex-1 min-h-0">
            {frameData ? (
              <FrameViewerCanvas
                bars={frameData.bars}
                dims={dims}
                highlightLength={highlightLength}
                governingBarIndex={frameData.check_report.load.governing_rail?.bar_index ?? null}
                frameKey={frameKey}
              />
            ) : (
              <div className="h-full flex items-center justify-center">
                <p className="text-sm text-muted">
                  Describe a frame in the left panel to get started.
                </p>
              </div>
            )}
          </div>

          {/* Bottom strip */}
          {frameData && <BottomStrip report={frameData.check_report} />}

          {/* Footer */}
          <footer
            className="shrink-0 px-4 py-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted"
            style={{ borderTop: "1px solid var(--rule)", background: "var(--surface)" }}
          >
            <a
              href="https://github.com/nati5174/FrameDesigner"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-text transition-colors"
            >
              GitHub
            </a>
            <span>
              Load results are estimates, not certified engineering. Check the design before you build or load it.
            </span>
          </footer>
        </div>

        {/* RIGHT column — total + tabs */}
        <aside
          className="w-[360px] shrink-0 flex flex-col bg-surface overflow-hidden"
          style={{ borderLeft: "1px solid var(--rule)" }}
        >
          {frameData ? (
            <RightPanel
              spec={spec}
              frameData={frameData}
              canUndo={false}
              activeTab={rightTab}
              onTabChange={setRightTab}
              onApply={handleApply}
              onUndo={() => {}}
              onCutListRowHover={setHighlightLength}
            />
          ) : (
            <p className="px-4 py-8 text-sm text-muted text-center">
              Generate a frame to see parts, cut plan, and load check.
            </p>
          )}
        </aside>
      </div>
    );
  }

  // ── Mobile + tablet layout ─────────────────────────────────────────────────

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
        {/* Desktop thread column (shown between sm and xl) */}
        {hasThread && (
          <aside className="hidden md:flex flex-col w-72 shrink-0 border-r border-border bg-background overflow-y-auto">
            <ConversationThread {...threadProps} />
            {isExampleState && (
              <div className="flex flex-col gap-3 px-3 py-4 border-t border-border">
                <p className="text-sm text-muted leading-relaxed">
                  Describe a frame. Get a 3D model, cut list, cost and load estimate.
                </p>
                <div className="flex flex-col gap-1.5">
                  <p className="text-xs text-muted">Try an example</p>
                  <div className="flex flex-wrap gap-2">
                    {EXAMPLES.map((ex) => (
                      <button
                        key={ex.prompt}
                        type="button"
                        onClick={() => handleExampleSelect(ex.prompt)}
                        className="px-3 py-1.5 rounded-full border border-border bg-surface text-sm text-text hover:border-accent hover:text-accent transition-colors"
                      >
                        {ex.label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </aside>
        )}

        {/* Viewer + side panel */}
        <div className="flex flex-col md:flex-row flex-1 min-h-0 min-w-0">
          {/* Viewer */}
          <main className="flex-1 min-w-0 min-h-48 md:min-h-0 p-3 pb-14 md:pb-3">
            {frameData ? (
              <div
                className="h-full w-full rounded-lg overflow-hidden"
                style={{ background: "var(--paper)" }}
              >
                <FrameViewerCanvas
                  bars={frameData.bars}
                  dims={dims}
                  highlightLength={highlightLength}
                  governingBarIndex={frameData.check_report.load.governing_rail?.bar_index ?? null}
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
          isExampleState={isExampleState}
          onExampleSelect={handleExampleSelect}
        />
      </div>

      {/* Footer */}
      <footer className="shrink-0 border-t border-border bg-surface px-4 py-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted">
        <a
          href="https://github.com/nati5174/FrameDesigner"
          target="_blank"
          rel="noopener noreferrer"
          className="hover:text-foreground transition-colors"
        >
          GitHub
        </a>
        <span>
          Load results are estimates, not certified engineering. Check the design before you build or load it.
        </span>
      </footer>
    </div>
  );
}
