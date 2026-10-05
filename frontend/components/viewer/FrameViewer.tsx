"use client";

import { Suspense, useEffect, useMemo } from "react";
import * as THREE from "three";
import { Canvas, useThree } from "@react-three/fiber";
import { OrbitControls, Grid, Bounds, useBounds, Html } from "@react-three/drei";
import type { BarData } from "@/lib/types";
import { toThree } from "@/lib/coordinates";
import { FrameBar } from "./FrameBar";

const MM = 1 / 1000;

// ─── Build-order delays ───────────────────────────────────────────────────────

const ROLE_GROUP: Record<string, number> = {
  leg: 0,               centre_leg: 0,
  bottom_rail_width: 1, bottom_rail_depth: 1,
  top_rail_width: 2,    top_rail_depth: 2,
  shelf_leg: 3,         shelf_rail_width: 3, shelf_rail_depth: 3,
};
const GROUP_BASE_MS = [0, 280, 480, 660];

function barsWithDelays(bars: BarData[]) {
  const counts = [0, 0, 0, 0];
  return bars.map((bar) => {
    const g = ROLE_GROUP[bar.role] ?? 2;
    const delay = GROUP_BASE_MS[g] + counts[g] * 55;
    counts[g]++;
    return { bar, delay };
  });
}

// ─── Camera auto-fit ──────────────────────────────────────────────────────────

function AutoFit({ bars }: { bars: BarData[] }) {
  const api = useBounds();
  const camera = useThree((s) => s.camera);

  useEffect(() => {
    if (bars.length === 0) return;

    // Fit the camera immediately from raw bar positions (scale-independent).
    // Bars start at scale=0 so we can't rely on Bounds here.
    const box = new THREE.Box3();
    for (const bar of bars) {
      for (const pt of [bar.start, bar.end]) {
        const [tx, ty, tz] = toThree(pt[0], pt[1], pt[2]);
        box.expandByPoint(new THREE.Vector3(tx * MM, ty * MM, tz * MM));
      }
    }
    if (!box.isEmpty()) {
      const center = new THREE.Vector3();
      const size = new THREE.Vector3();
      box.getCenter(center);
      box.getSize(size);
      const maxDim = Math.max(size.x, size.y, size.z);
      const fov = ((camera as THREE.PerspectiveCamera).fov * Math.PI) / 180;
      const dist = (maxDim * 0.5) / Math.tan(fov * 0.5) * 1.5;
      camera.position.set(
        center.x + dist * 0.55,
        center.y + dist * 0.45,
        center.z + dist * 0.7,
      );
      camera.lookAt(center);
    }

    // Re-fit via Bounds API after animation completes (~850 ms)
    const t = setTimeout(() => api.refresh().fit(), 850);
    return () => clearTimeout(t);
  }, [bars, api, camera]);

  return null;
}

// ─── Dimension labels ─────────────────────────────────────────────────────────

interface DimsProps {
  bars: BarData[];
  dims: { widthMm: number; depthMm: number; heightMm: number };
}

// ─── Dimension labels (HTML overlay — fixed 13px size at any zoom) ───────────

const LABEL_STYLE: React.CSSProperties = {
  fontSize: "13px",
  fontFamily: "var(--font-ibm-plex-mono), ui-monospace, monospace",
  color: "var(--ink)",
  background: "var(--surface)",
  border: "1px solid var(--rule)",
  padding: "2px 6px",
  whiteSpace: "nowrap",
  pointerEvents: "none",
  userSelect: "none",
};

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
  const GAP = 0.07;

  return (
    <>
      {/* Width — below front bottom edge, centred X */}
      <Html
        position={[(min.x + max.x) / 2, min.y - GAP * 0.9, max.z + GAP * 0.4]}
        center
        zIndexRange={[100, 0]}
      >
        <div style={LABEL_STYLE}>{`${dims.widthMm} mm`}</div>
      </Html>

      {/* Depth — right of right-bottom edge, centred Z */}
      <Html
        position={[max.x + GAP * 0.6, min.y - GAP * 0.9, (min.z + max.z) / 2]}
        center
        zIndexRange={[100, 0]}
      >
        <div style={LABEL_STYLE}>{`${dims.depthMm} mm`}</div>
      </Html>

      {/* Height — left of front-left edge, centred Y */}
      <Html
        position={[min.x - GAP * 0.6, (min.y + max.y) / 2, max.z + GAP * 0.4]}
        center
        zIndexRange={[100, 0]}
      >
        <div style={LABEL_STYLE}>{`${dims.heightMm} mm`}</div>
      </Html>
    </>
  );
}

// ─── Canvas ───────────────────────────────────────────────────────────────────

export interface FrameViewerProps {
  bars: BarData[];
  dims?: { widthMm: number; depthMm: number; heightMm: number };
  highlightLength: number | null;
  governingBarIndex: number | null;
  /** Increments on each new frame load — forces bars to remount and replay animation. */
  frameKey: number;
}

export function FrameViewer({ bars, dims, highlightLength, governingBarIndex, frameKey }: FrameViewerProps) {
  const entries = useMemo(() => barsWithDelays(bars), [bars]);

  return (
    <Canvas
      gl={{ alpha: true }}
      camera={{ position: [2.5, 1.8, 2.5], fov: 45, near: 0.01, far: 100 }}
      style={{ width: "100%", height: "100%" }}
    >
      <ambientLight intensity={0.6} />
      <directionalLight position={[4, 6, 3]} intensity={1.2} castShadow />
      <directionalLight position={[-3, 2, -2]} intensity={0.3} />

      <Bounds fit clip observe>
        <AutoFit bars={bars} />
        {entries.map(({ bar, delay }, i) => (
          <FrameBar
            key={`${frameKey}-${i}`}
            start={bar.start}
            end={bar.end}
            profileWidthMm={bar.profile_width_mm}
            role={bar.role}
            barIndex={i}
            highlightLength={highlightLength}
            governingBarIndex={governingBarIndex}
            animDelay={delay}
          />
        ))}
      </Bounds>

      {dims && <DimensionLabels bars={bars} dims={dims} />}

      <Grid
        args={[10, 10]}
        position={[0, -0.001, 0]}
        cellColor="#d0d6dc"
        sectionColor="#c0c8ce"
        cellSize={0.1}
        sectionSize={0.5}
        fadeDistance={4}
        infiniteGrid
      />

      <OrbitControls makeDefault enableDamping dampingFactor={0.1} />
    </Canvas>
  );
}

export function FrameViewerCanvas({
  bars, dims, highlightLength, governingBarIndex, frameKey,
}: FrameViewerProps) {
  return (
    <Suspense fallback={<ViewerFallback text="Loading viewer…" />}>
      <FrameViewer
        bars={bars}
        dims={dims}
        highlightLength={highlightLength}
        governingBarIndex={governingBarIndex}
        frameKey={frameKey}
      />
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
