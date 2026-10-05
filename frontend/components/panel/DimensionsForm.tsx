"use client";

import { useState } from "react";
import type { FrameSpec } from "@/lib/types";
import { Spinner } from "@/components/ui/Spinner";

interface DimensionsFormProps {
  spec: FrameSpec;
  loading: boolean;
  onGenerate: (spec: FrameSpec) => void;
}

const PROFILE_OPTIONS = [
  { value: "20-series", label: "20 series (20×20 mm)" },
  { value: "30-series", label: "30 series (30×30 mm)" },
  { value: "40-series", label: "40 series (40×40 mm)" },
  { value: "45-series", label: "45 series (45×45 mm)" },
] as const;

type Draft = {
  frame_type: "table" | "shelf_unit";
  profile_series: string;
  width_mm: string;
  depth_mm: string;
  height_mm: string;
  // table
  shelf_height_mm: string;
  target_load_kg: string;
  // shelf unit
  level_count: string;
  load_per_level_kg: string;
  centre_legs: boolean;
};

function evenly(h: number, n: number): number[] {
  const levels: number[] = [];
  for (let i = 1; i <= n; i++) levels.push(Math.round((h * i) / n));
  levels[levels.length - 1] = h; // exact top
  return levels;
}

function toDraft(s: FrameSpec): Draft {
  const isShelf = s.frame_type === "shelf_unit";
  return {
    frame_type: s.frame_type,
    profile_series: s.profile_series ?? "40-series",
    width_mm: String(s.width_mm),
    depth_mm: String(s.depth_mm),
    height_mm: String(s.height_mm),
    shelf_height_mm: s.shelf_height_mm != null ? String(s.shelf_height_mm) : "",
    target_load_kg: s.target_load_kg != null ? String(s.target_load_kg) : "100",
    level_count: isShelf && s.level_heights_mm ? String(s.level_heights_mm.length) : "3",
    load_per_level_kg:
      s.load_per_level_kg != null ? String(s.load_per_level_kg) : "30",
    centre_legs: s.centre_legs,
  };
}

function fromDraft(d: Draft): FrameSpec | null {
  const w = parseInt(d.width_mm, 10);
  const dep = parseInt(d.depth_mm, 10);
  const h = parseInt(d.height_mm, 10);
  if (isNaN(w) || w < 1 || isNaN(dep) || dep < 1 || isNaN(h) || h < 1) return null;

  const series = d.profile_series || "40-series";

  if (d.frame_type === "shelf_unit") {
    const n = Math.max(3, Math.min(10, parseInt(d.level_count, 10) || 3));
    const perLevel = parseFloat(d.load_per_level_kg);
    if (isNaN(perLevel) || perLevel <= 0) return null;
    const levels = evenly(h, n);
    return {
      frame_type: "shelf_unit",
      width_mm: w,
      depth_mm: dep,
      height_mm: h,
      profile_series: series,
      shelf_height_mm: null,
      target_load_kg: null,
      centre_legs: d.centre_legs,
      level_heights_mm: levels,
      load_per_level_kg: perLevel,
    };
  }

  const load = parseFloat(d.target_load_kg);
  if (isNaN(load) || load < 0) return null;
  const shelf = d.shelf_height_mm.trim() ? parseInt(d.shelf_height_mm, 10) : null;
  if (shelf !== null && isNaN(shelf)) return null;

  return {
    frame_type: "table",
    width_mm: w,
    depth_mm: dep,
    height_mm: h,
    shelf_height_mm: shelf,
    profile_series: series,
    target_load_kg: load,
    centre_legs: d.centre_legs,
    level_heights_mm: null,
    load_per_level_kg: null,
  };
}

const LABEL = "text-xs text-muted mb-0.5 block";
const INPUT =
  "w-full rounded border border-border bg-surface px-2 py-1 text-sm text-text font-mono";

export function DimensionsForm({ spec, loading, onGenerate }: DimensionsFormProps) {
  const [draft, setDraft] = useState<Draft>(toDraft(spec));
  const [prevSpec, setPrevSpec] = useState(spec);

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
  const isShelf = draft.frame_type === "shelf_unit";

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-3">
      {/* Frame type selector */}
      <div className="flex gap-1 rounded-md border border-border overflow-hidden text-xs">
        {(["table", "shelf_unit"] as const).map((ft) => (
          <button
            key={ft}
            type="button"
            onClick={() => set("frame_type", ft)}
            className={`flex-1 py-1.5 font-medium transition-colors ${
              draft.frame_type === ft
                ? "bg-ink text-surface"
                : "text-muted hover:text-text"
            }`}
          >
            {ft === "table" ? "Table" : "Shelf unit"}
          </button>
        ))}
      </div>

      {/* Profile series */}
      <div>
        <label className={LABEL}>Profile series</label>
        <select
          className={INPUT}
          value={draft.profile_series}
          onChange={(e) => set("profile_series", e.target.value)}
        >
          {PROFILE_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      </div>

      {/* W / D / H */}
      <div className="grid grid-cols-3 gap-2">
        {(["width_mm", "depth_mm", "height_mm"] as const).map((k) => (
          <div key={k}>
            <label className={LABEL}>
              {k === "width_mm" ? "Width" : k === "depth_mm" ? "Depth" : "Height"} (mm)
            </label>
            <input
              className={INPUT}
              type="number"
              min={1}
              value={draft[k]}
              onChange={(e) => set(k, e.target.value)}
            />
          </div>
        ))}
      </div>

      {isShelf ? (
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className={LABEL}>Level count</label>
            <input
              className={INPUT}
              type="number"
              min={3}
              max={10}
              value={draft.level_count}
              onChange={(e) => set("level_count", e.target.value)}
            />
          </div>
          <div>
            <label className={LABEL}>Load / level (kg)</label>
            <input
              className={INPUT}
              type="number"
              min={1}
              value={draft.load_per_level_kg}
              onChange={(e) => set("load_per_level_kg", e.target.value)}
            />
          </div>
        </div>
      ) : (
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
      )}

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
          bg-ink px-4 py-2 text-sm font-medium text-surface
          hover:opacity-90 disabled:opacity-50 transition-colors
        "
      >
        {loading && <Spinner size="sm" />}
        {loading ? "Generating…" : "Generate"}
      </button>
    </form>
  );
}
