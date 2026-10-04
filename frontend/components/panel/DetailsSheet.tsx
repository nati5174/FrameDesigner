"use client";

import { useState } from "react";
import type { FixCandidate, FrameResponse, FrameSpec } from "@/lib/types";
import { CollapsibleSection } from "@/components/panel/CollapsibleSection";
import { CutList } from "@/components/panel/CutList";
import { DimensionsForm } from "@/components/panel/DimensionsForm";
import { LoadCheck } from "@/components/panel/LoadCheck";
import { Suggestions } from "@/components/panel/Suggestions";
import { SuggestionCard } from "@/components/panel/SuggestionCard";

interface Props {
  spec: FrameSpec | null;
  frameData: FrameResponse | null;
  loading: boolean;
  canUndo: boolean;
  onGenerate: (spec: FrameSpec) => void;
  onApply: (candidate: FixCandidate) => void;
  onUndo: () => void;
  onCutListRowHover?: (lengthMm: number | null) => void;
}

/**
 * Mobile-only slide-up details sheet.
 * A small toggle button sits above the ThreadSheet handle.
 * Tapping it slides up the details panel (dimensions, load check, cut list, suggestions).
 */
export function DetailsSheet({
  spec,
  frameData,
  loading,
  canUndo,
  onGenerate,
  onApply,
  onUndo,
  onCutListRowHover,
}: Props) {
  const [open, setOpen] = useState(false);
  const hasContent = spec !== null || frameData !== null;

  if (!hasContent) return null;

  return (
    <>
      {/* Toggle button — sits above the ThreadSheet handle (bottom-12 + gap) */}
      {!open && (
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="
            fixed bottom-14 right-4 z-30
            rounded-full border border-border bg-surface
            px-3 py-1.5 text-xs font-medium text-text shadow-md
            hover:bg-accent hover:text-accent-fg transition-colors
          "
        >
          Details ▴
        </button>
      )}

      {open && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-30 bg-black/30"
            onClick={() => setOpen(false)}
            aria-hidden="true"
          />

          {/* Sheet */}
          <div className="fixed inset-x-0 bottom-0 z-40 flex flex-col bg-surface border-t border-border rounded-t-xl shadow-xl max-h-[75vh]">
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-border shrink-0">
              <span className="text-sm font-medium text-text">Details</span>
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="text-xs text-muted hover:text-text"
              >
                Close
              </button>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto">
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
                      totalCostUsd={frameData.cut_list_total_cost_usd}
                      totalWeightKg={frameData.cut_list_total_weight_kg}
                      onRowHover={onCutListRowHover}
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
            </div>
          </div>
        </>
      )}
    </>
  );
}
