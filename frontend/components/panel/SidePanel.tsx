"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { FixCandidate, FrameResponse, FrameSpec } from "@/lib/types";
import { CollapsibleSection } from "@/components/panel/CollapsibleSection";
import { DimensionsForm } from "@/components/panel/DimensionsForm";
import { CutList } from "@/components/panel/CutList";
import { LoadCheck } from "@/components/panel/LoadCheck";
import { PartsList } from "@/components/panel/PartsList";
import { Suggestions } from "@/components/panel/Suggestions";
import { SuggestionCard } from "@/components/panel/SuggestionCard";

interface SidePanelProps {
  spec: FrameSpec | null;
  frameData: FrameResponse | null;
  loading: boolean;
  canUndo: boolean;
  onGenerate: (spec: FrameSpec) => void;
  onApply: (candidate: FixCandidate) => void;
  onUndo: () => void;
  onCutListRowHover?: (lengthMm: number | null) => void;
}

const MIN_W  = 200;
const MAX_W  = 540;
const DEF_W  = 320;

export function SidePanel({
  spec,
  frameData,
  loading,
  canUndo,
  onGenerate,
  onApply,
  onUndo,
  onCutListRowHover,
}: SidePanelProps) {
  const [width, setWidth]         = useState(DEF_W);
  const [collapsed, setCollapsed] = useState(false);
  const [isMobile, setIsMobile]   = useState(false);
  const dragging = useRef(false);
  const startX   = useRef(0);
  const startW   = useRef(0);

  // Detect mobile breakpoint
  useEffect(() => {
    const check = () => setIsMobile(window.innerWidth < 768);
    check();
    window.addEventListener("resize", check);
    return () => window.removeEventListener("resize", check);
  }, []);

  const onMouseDown = useCallback(
    (e: React.MouseEvent) => {
      dragging.current = true;
      startX.current   = e.clientX;
      startW.current   = width;

      function onMove(ev: MouseEvent) {
        if (!dragging.current) return;
        const delta = startX.current - ev.clientX;
        setWidth(Math.min(MAX_W, Math.max(MIN_W, startW.current + delta)));
      }
      function onUp() {
        dragging.current = false;
        window.removeEventListener("mousemove", onMove);
        window.removeEventListener("mouseup", onUp);
      }
      window.addEventListener("mousemove", onMove);
      window.addEventListener("mouseup", onUp);
    },
    [width]
  );

  const hasContent = spec || frameData;

  // Mobile: full-width strip below viewer, max-height, scroll
  if (isMobile) {
    return (
      <aside className="
        w-full shrink-0 border-t border-border bg-surface
        overflow-y-auto
        max-h-[45vh]
      ">
        {hasContent ? (
          <PanelContent
            spec={spec}
            frameData={frameData}
            loading={loading}
            canUndo={canUndo}
            onGenerate={onGenerate}
            onApply={onApply}
            onUndo={onUndo}
            onCutListRowHover={onCutListRowHover}
          />
        ) : (
          <p className="px-4 py-6 text-sm text-muted text-center">
            Enter a description above to get started.
          </p>
        )}
      </aside>
    );
  }

  // Desktop: collapsible + resizable side panel
  return (
    <aside
      style={{ width: collapsed ? 0 : width }}
      className="
        relative flex shrink-0 flex-col
        border-l border-border bg-surface
        transition-[width] overflow-hidden
      "
    >
      {/* Resize handle — left edge */}
      {!collapsed && (
        <div
          onMouseDown={onMouseDown}
          aria-hidden="true"
          className="
            absolute left-0 top-0 h-full w-1.5 cursor-col-resize
            hover:bg-accent/30 active:bg-accent/50 z-10
          "
        />
      )}

      {/* Collapse toggle */}
      <button
        type="button"
        onClick={() => setCollapsed((v) => !v)}
        aria-label={collapsed ? "Expand panel" : "Collapse panel"}
        className="
          absolute -left-7 top-1/2 -translate-y-1/2
          flex h-6 w-6 items-center justify-center
          rounded-l border border-r-0 border-border bg-surface
          text-xs text-muted hover:text-text z-10
        "
      >
        {collapsed ? "›" : "‹"}
      </button>

      {!collapsed && (
        <div className="flex flex-col overflow-y-auto h-full">
          {hasContent ? (
            <PanelContent
              spec={spec}
              frameData={frameData}
              loading={loading}
              canUndo={canUndo}
              onGenerate={onGenerate}
              onApply={onApply}
              onUndo={onUndo}
              onCutListRowHover={onCutListRowHover}
            />
          ) : (
            <p className="px-4 py-8 text-sm text-muted text-center">
              Enter a description above to get started.
            </p>
          )}
        </div>
      )}
    </aside>
  );
}

// ─── Shared content ───────────────────────────────────────────────────────────

interface PanelContentProps {
  spec: FrameSpec | null;
  frameData: FrameResponse | null;
  loading: boolean;
  canUndo: boolean;
  onGenerate: (spec: FrameSpec) => void;
  onApply: (candidate: FixCandidate) => void;
  onUndo: () => void;
  onCutListRowHover?: (lengthMm: number | null) => void;
}

function PanelContent({
  spec, frameData, loading, canUndo,
  onGenerate, onApply, onUndo, onCutListRowHover,
}: PanelContentProps) {
  return (
    <>
      {spec && (
        <CollapsibleSection title="Dimensions">
          <DimensionsForm spec={spec} loading={loading} onGenerate={onGenerate} />
        </CollapsibleSection>
      )}

      {frameData && (
        <>
          <CollapsibleSection title="Load check">
            <LoadCheck checkReport={frameData.check_report} />
          </CollapsibleSection>

          {frameData.suggestions.length > 0 && (
            <CollapsibleSection title="Suggestions">
              <Suggestions
                candidates={frameData.suggestions}
                canUndo={canUndo}
                onApply={onApply}
                onUndo={onUndo}
              />
            </CollapsibleSection>
          )}

          <CollapsibleSection title="Cut list" defaultOpen={false}>
            <CutList
              rows={frameData.cut_list}
              totalCostUsd={frameData.cut_list_total_cost_usd}
              totalWeightKg={frameData.cut_list_total_weight_kg}
              onRowHover={onCutListRowHover}
            />
          </CollapsibleSection>

          <CollapsibleSection title="Parts list" defaultOpen={false}>
            <PartsList
              rows={frameData.parts_list ?? []}
              hardwareCostUsd={frameData.hardware_cost_usd ?? null}
              hardwareWeightKg={frameData.hardware_weight_kg ?? null}
              barsCostUsd={frameData.cut_list_total_cost_usd}
              barsWeightKg={frameData.cut_list_total_weight_kg}
              totalCostUsd={frameData.total_cost_usd ?? null}
              totalWeightKg={frameData.total_weight_kg ?? null}
              hardwarePriced={frameData.hardware_priced ?? false}
            />
          </CollapsibleSection>

          {frameData.cost_suggestion && (
            <CollapsibleSection title="Cost saving">
              <SuggestionCard
                candidate={frameData.cost_suggestion}
                canUndo={canUndo}
                onApply={onApply}
                onUndo={onUndo}
              />
            </CollapsibleSection>
          )}
        </>
      )}
    </>
  );
}
