import { useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { toThree } from "@/lib/coordinates";

const MM = 1 / 1000;

// Single neutral tone for all bars — governing rail gets accent via governingBarIndex.
function roleColor(_role: string): string {
  return "#5A6E82";
}

/** Ease-out cubic. */
function easeOut(t: number): number {
  return 1 - Math.pow(1 - t, 3);
}

interface FrameBarProps {
  start: [number, number, number];
  end: [number, number, number];
  profileWidthMm: number;
  role: string;
  barIndex: number;
  highlightLength: number | null;
  governingBarIndex: number | null;
  /** Delay before this bar's entrance animation starts (ms). */
  animDelay: number;
}

export function FrameBar({
  start,
  end,
  profileWidthMm,
  role,
  barIndex,
  highlightLength,
  governingBarIndex,
  animDelay,
}: FrameBarProps) {
  const meshRef = useRef<THREE.Mesh>(null!);
  const startT = useRef<number | null>(null);

  // Compute geometry once
  const [sx, sy, sz] = toThree(start[0], start[1], start[2]);
  const [ex, ey, ez] = toThree(end[0], end[1], end[2]);
  const startV = new THREE.Vector3(sx * MM, sy * MM, sz * MM);
  const endV   = new THREE.Vector3(ex * MM, ey * MM, ez * MM);
  const dir    = endV.clone().sub(startV);
  const length = dir.length();

  // Length in original mm for cut-list matching
  const dx = end[0] - start[0];
  const dy = end[1] - start[1];
  const dz = end[2] - start[2];
  const lengthMm = Math.sqrt(dx * dx + dy * dy + dz * dz);

  const center = startV.clone().add(endV).multiplyScalar(0.5);
  const quat   = new THREE.Quaternion();
  if (length > 1e-9) {
    quat.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir.normalize());
  }
  const w = profileWidthMm * MM;

  // Build-order entrance animation
  useFrame(({ clock }) => {
    if (!meshRef.current) return;
    const now = clock.getElapsedTime();
    if (startT.current === null) startT.current = now + animDelay / 1000;
    const t = Math.max(0, Math.min(1, (now - startT.current) / 0.22));
    meshRef.current.scale.setScalar(easeOut(t));
  });

  if (length < 1e-9) return null;

  const lit =
    highlightLength !== null && Math.abs(lengthMm - highlightLength) < 0.5;
  const isGoverning = governingBarIndex !== null && barIndex === governingBarIndex;

  const color = lit ? "#FFD54F" : isGoverning ? "#C2410C" : roleColor(role);
  const emissive = lit ? "#E65C00" : isGoverning ? "#7A2008" : "#000000";
  const emissiveIntensity = lit ? 0.35 : isGoverning ? 0.25 : 0;

  return (
    <mesh ref={meshRef} position={center} quaternion={quat} scale={0}>
      <boxGeometry args={[w, length, w]} />
      <meshStandardMaterial
        color={color}
        emissive={emissive}
        emissiveIntensity={emissiveIntensity}
        roughness={0.5}
        metalness={0.3}
      />
    </mesh>
  );
}
