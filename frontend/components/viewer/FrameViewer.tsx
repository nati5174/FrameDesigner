"use client";

import { Suspense, useEffect, useMemo } from "react";
import * as THREE from "three";
import { Canvas } from "@react-three/fiber";
import { OrbitControls, Grid, Bounds, useBounds, Html } from "@react-three/drei";
import type { BarData } from "@/lib/types";
import { toThree } from "@/lib/coordinates";
import { FrameBar } from "./FrameBar";

const MM = 1 / 1000;

// ─── Auto-fit ────────────────────────────────────────────────────────────────

function AutoFit({ bars }: { bars: BarData[] }) {
  const api = useBounds();
  useEffect(() => {
    if (bars.length > 0) api.refresh().fit();
  }, [bars, api]);
  return null;
}

// ─── Dimension labels ─────────────────────────────────────────────────────────

interface DimsProps {
  bars: BarData[];
  dims: { widthMm: number; depthMm: number; heightMm: number };
}

function DimensionLabels({ bars, dims }: DimsProps) {
  const bbox = useMemo(() => {
    if (bars.length === 0) return null;
    const box = new THREE.Box3();
    for (const bar of bars) {
      for (const pt of [bar.start, bar.end]) {
        const [tx, ty, tz] = toThree(pt[0], pt[1], pt[2]);
        box.expandByPoint(new THREE.Vector3(tx * MM, ty * MM, tz * MM));
      }
    }
    return box;
  }, [bars]);

  if (!bbox) return null;

  const { min, max } = bbox;
  const GAP = 0.07; // 70 mm clearance from frame face

  return (
    <>
      {/* Width — below front bottom edge, centred X */}
      <Html
        center
        zIndexRange={[0, 0]}
        position={[(min.x + max.x) / 2, min.y - GAP * 0.6, max.z + GAP]}
      >
        <DimPill axis="W">{dims.widthMm.toLocaleString()} mm</DimPill>
      </Html>

      {/* Depth — right of right-bottom edge, centred Z */}
      <Html
        center
        zIndexRange={[0, 0]}
        position={[max.x + GAP, min.y - GAP * 0.6, (min.z + max.z) / 2]}
      >
        <DimPill axis="D">{dims.depthMm.toLocaleString()} mm</DimPill>
      </Html>

      {/* Height — left of front-left edge, centred Y */}
      <Html
        center
        zIndexRange={[0, 0]}
        position={[min.x - GAP, (min.y + max.y) / 2, max.z + GAP]}
      >
        <DimPill axis="H">{dims.heightMm.toLocaleString()} mm</DimPill>
      </Html>
    </>
  );
}

function DimPill({
  axis,
  children,
}: {
  axis: string;
  children: React.ReactNode;
}) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        background: "rgba(15,15,20,0.72)",
        color: "#E6E3DD",
        padding: "2px 8px",
        borderRadius: 99,
        fontSize: 11,
        fontFamily: "monospace",
        whiteSpace: "nowrap",
        backdropFilter: "blur(4px)",
        border: "1px solid rgba(255,255,255,0.10)",
        pointerEvents: "none",
        userSelect: "none",
      }}
    >
      <span style={{ color: "#8A8880", fontSize: 10 }}>{axis}</span>
      {children}
    </span>
  );
}

// ─── Canvas ───────────────────────────────────────────────────────────────────

export interface FrameViewerProps {
  bars: BarData[];
  dims?: { widthMm: number; depthMm: number; heightMm: number };
  /** When set, bars whose length matches (±0.5 mm) glow amber. */
  highlightLength: number | null;
}

export function FrameViewer({ bars, dims, highlightLength }: FrameViewerProps) {
  return (
    <Canvas
      camera={{ position: [2.5, 1.8, 2.5], fov: 45, near: 0.01, far: 100 }}
      style={{ width: "100%", height: "100%" }}
    >
      <ambientLight intensity={0.6} />
      <directionalLight position={[4, 6, 3]} intensity={1.2} castShadow />
      <directionalLight position={[-3, 2, -2]} intensity={0.3} />

      <Bounds fit clip observe>
        <AutoFit bars={bars} />
        {bars.map((bar, i) => (
          <FrameBar
            key={i}
            start={bar.start}
            end={bar.end}
            profileWidthMm={bar.profile_width_mm}
            role={bar.role}
            highlightLength={highlightLength}
          />
        ))}
      </Bounds>

      {dims && <DimensionLabels bars={bars} dims={dims} />}

      <Grid
        args={[10, 10]}
        position={[0, -0.001, 0]}
        cellColor="#cccccc"
        sectionColor="#aaaaaa"
        cellSize={0.1}
        sectionSize={0.5}
        fadeDistance={6}
        infiniteGrid
      />

      <OrbitControls makeDefault enableDamping dampingFactor={0.1} />
    </Canvas>
  );
}

export function FrameViewerCanvas({
  bars,
  dims,
  highlightLength,
}: FrameViewerProps) {
  return (
    <Suspense fallback={<ViewerFallback text="Loading viewer…" />}>
      <FrameViewer bars={bars} dims={dims} highlightLength={highlightLength} />
    </Suspense>
  );
}

function ViewerFallback({ text }: { text: string }) {
  return (
    <div className="flex h-full w-full items-center justify-center rounded-lg border border-border bg-surface text-muted text-sm">
      {text}
    </div>
  );
}
