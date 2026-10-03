"use client";

import { useCallback, useRef, useState } from "react";
import type { FixCandidate, FrameResponse, FrameSpec } from "@/lib/types";
import { CollapsibleSection } from "@/components/panel/CollapsibleSection";
import { DimensionsForm } from "@/components/panel/DimensionsForm";
import { CutList } from "@/components/panel/CutList";
import { LoadCheck } from "@/components/panel/LoadCheck";
import { Suggestions } from "@/components/panel/Suggestions";
import { ExampleChips } from "@/components/ui/ExampleChips";

interface SidePanelProps {
  spec: FrameSpec | null;
  frameData: FrameResponse | null;
  loading: boolean;
  canUndo: boolean;
  onGenerate: (spec: FrameSpec) => void;
  onApply: (candidate: FixCandidate) => void;
  onUndo: () => void;
  onExampleSelect: (prompt: string) => void;
  onCutListRowHover?: (lengthMm: number | null) => void;
}

const MIN_WIDTH = 200;
const MAX_WIDTH = 520;
const DEFAULT_WIDTH = 320;

export function SidePanel({
  spec,
  frameData,
  loading,
  canUndo,
  onGenerate,
  onApply,
  onUndo,
  onExampleSelect,
  onCutListRowHover,
}: SidePanelProps) {
  const [width, setWidth] = useState(DEFAULT_WIDTH);
  const [collapsed, setCollapsed] = useState(false);
  const dragging = useRef(false);
  const startX = useRef(0);
  const startW = useRef(0);

  const onMouseDown = useCallback((e: React.MouseEvent) => {
    dragging.current = true;
    startX.current = e.clientX;
    startW.current = width;

    function onMove(ev: MouseEvent) {
      if (!dragging.current) return;
      const delta = startX.current - ev.clientX;
      setWidth(Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, startW.current + delta)));
    }
    function onUp() {
      dragging.current = false;
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    }
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  }, [width]);

  return (
    <aside
      style={{ width: collapsed ? 0 : width }}
      className="relative flex shrink-0 flex-col border-l border-border bg-surface transition-[width] overflow-hidden"
    >
      {/* Resize handle — left edge */}
      {!collapsed && (
        <div
          onMouseDown={onMouseDown}
          aria-hidden="true"
          className="
            absolute left-0 top-0 h-full w-1.5 cursor-col-resize
            hover:bg-accent/30 active:bg-accent/50
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
          text-xs text-muted hover:text-text
          z-10
        "
      >
        {collapsed ? "›" : "‹"}
      </button>

      {!collapsed && (
        <div className="flex flex-col overflow-y-auto h-full">
          {!spec && !frameData && (
            <ExampleChips onSelect={onExampleSelect} />
          )}

          {spec && (
            <CollapsibleSection title="Dimensions">
              <DimensionsForm
                spec={spec}
                loading={loading}
                onGenerate={onGenerate}
              />
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
                  onRowHover={onCutListRowHover}
                />
              </CollapsibleSection>
            </>
          )}
        </div>
      )}
    </aside>
  );
}
