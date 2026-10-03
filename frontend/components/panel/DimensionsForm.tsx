"use client";

import { useState } from "react";
import type { FrameSpec } from "@/lib/types";
import { Spinner } from "@/components/ui/Spinner";

interface DimensionsFormProps {
  spec: FrameSpec;
  loading: boolean;
  onGenerate: (spec: FrameSpec) => void;
}

type Draft = {
  width_mm: string;
  depth_mm: string;
  height_mm: string;
  shelf_height_mm: string;
  profile_series: string;
  target_load_kg: string;
  centre_legs: boolean;
};

function toDraft(s: FrameSpec): Draft {
  return {
    width_mm: String(s.width_mm),
    depth_mm: String(s.depth_mm),
    height_mm: String(s.height_mm),
    shelf_height_mm: s.shelf_height_mm !== null ? String(s.shelf_height_mm) : "",
    profile_series: s.profile_series,
    target_load_kg: String(s.target_load_kg),
    centre_legs: s.centre_legs,
  };
}

function fromDraft(d: Draft): FrameSpec | null {
  const w = parseInt(d.width_mm, 10);
  const dep = parseInt(d.depth_mm, 10);
  const h = parseInt(d.height_mm, 10);
  const load = parseInt(d.target_load_kg, 10);
  if (
    isNaN(w) || w < 1 ||
    isNaN(dep) || dep < 1 ||
    isNaN(h) || h < 1 ||
    isNaN(load) || load < 0
  ) return null;

  const shelf = d.shelf_height_mm.trim()
    ? parseInt(d.shelf_height_mm, 10)
    : null;
  if (shelf !== null && isNaN(shelf)) return null;

  return {
    width_mm: w,
    depth_mm: dep,
    height_mm: h,
    shelf_height_mm: shelf,
    profile_series: d.profile_series,
    target_load_kg: load,
    centre_legs: d.centre_legs,
  };
}

const LABEL = "text-xs text-muted mb-0.5 block";
const INPUT =
  "w-full rounded border border-border bg-bg px-2 py-1 text-sm text-text font-mono";

export function DimensionsForm({ spec, loading, onGenerate }: DimensionsFormProps) {
  const [draft, setDraft] = useState<Draft>(toDraft(spec));
  const [prevSpec, setPrevSpec] = useState(spec);

  // Keep draft in sync when spec changes externally (e.g. from PromptBar or Apply)
  if (prevSpec !== spec) {
    setPrevSpec(spec);
    setDraft(toDraft(spec));
  }

  function set<K extends keyof Draft>(key: K, value: Draft[K]) {
    setDraft((d) => ({ ...d, [key]: value }));
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const s = fromDraft(draft);
    if (s) onGenerate(s);
  }

  const valid = fromDraft(draft) !== null;

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-3">
      <div className="grid grid-cols-3 gap-2">
        <div>
          <label className={LABEL}>Width (mm)</label>
          <input
            className={INPUT}
            type="number"
            min={1}
            value={draft.width_mm}
            onChange={(e) => set("width_mm", e.target.value)}
          />
        </div>
        <div>
          <label className={LABEL}>Depth (mm)</label>
          <input
            className={INPUT}
            type="number"
            min={1}
            value={draft.depth_mm}
            onChange={(e) => set("depth_mm", e.target.value)}
          />
        </div>
        <div>
          <label className={LABEL}>Height (mm)</label>
          <input
            className={INPUT}
            type="number"
            min={1}
            value={draft.height_mm}
            onChange={(e) => set("height_mm", e.target.value)}
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className={LABEL}>Load (kg)</label>
          <input
            className={INPUT}
            type="number"
            min={0}
            value={draft.target_load_kg}
            onChange={(e) => set("target_load_kg", e.target.value)}
          />
        </div>
        <div>
          <label className={LABEL}>Shelf height (mm)</label>
          <input
            className={INPUT}
            type="number"
            min={1}
            placeholder="none"
            value={draft.shelf_height_mm}
            onChange={(e) => set("shelf_height_mm", e.target.value)}
          />
        </div>
      </div>

      <div className="flex items-center gap-2">
        <input
          id="centre-legs"
          type="checkbox"
          checked={draft.centre_legs}
          onChange={(e) => set("centre_legs", e.target.checked)}
          className="h-3.5 w-3.5 accent-accent"
        />
        <label htmlFor="centre-legs" className="text-sm text-text select-none">
          Centre legs
        </label>
      </div>

      <button
        type="submit"
        disabled={loading || !valid}
        className="
          flex items-center justify-center gap-2 rounded-md
          bg-accent px-4 py-2 text-sm font-medium text-accent-fg
          hover:bg-accent-hover disabled:opacity-50 transition-colors
        "
      >
        {loading && <Spinner size="sm" />}
        {loading ? "Generating…" : "Generate"}
      </button>
    </form>
  );
}
