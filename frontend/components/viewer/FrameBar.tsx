import { useMemo } from "react";
import * as THREE from "three";
import { toThree } from "@/lib/coordinates";

const MM = 1 / 1000; // mm → metres

function roleColor(role: string): string {
  if (role === "leg" || role === "centre_leg") return "#4A7FB5";
  if (role.includes("shelf")) return "#C8963C";
  if (role.includes("depth")) return "#7DB3D5";
  return "#6B9EC4";
}

interface FrameBarProps {
  start: [number, number, number];
  end: [number, number, number];
  profileWidthMm: number;
  role: string;
  /** When set, bars whose length matches (±0.5 mm) glow amber. */
  highlightLength: number | null;
}

export function FrameBar({
  start,
  end,
  profileWidthMm,
  role,
  highlightLength,
}: FrameBarProps) {
  const { position, quaternion, length, lengthMm, w } = useMemo(() => {
    const [sx, sy, sz] = toThree(start[0], start[1], start[2]);
    const [ex, ey, ez] = toThree(end[0], end[1], end[2]);

    const startV = new THREE.Vector3(sx * MM, sy * MM, sz * MM);
    const endV   = new THREE.Vector3(ex * MM, ey * MM, ez * MM);

    const dir = endV.clone().sub(startV);
    const len = dir.length();

    // Length in original mm for cut-list matching (no scale applied)
    const dx = end[0] - start[0];
    const dy = end[1] - start[1];
    const dz = end[2] - start[2];
    const lenMm = Math.sqrt(dx * dx + dy * dy + dz * dz);

    const center = startV.clone().add(endV).multiplyScalar(0.5);

    const quat = new THREE.Quaternion();
    if (len > 1e-9) {
      quat.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir.normalize());
    }

    return {
      position: center,
      quaternion: quat,
      length: len,
      lengthMm: lenMm,
      w: profileWidthMm * MM,
    };
  }, [start, end, profileWidthMm]);

  if (length < 1e-9) return null;

  const lit = highlightLength !== null && Math.abs(lengthMm - highlightLength) < 0.5;

  return (
    <mesh position={position} quaternion={quaternion}>
      <boxGeometry args={[w, length, w]} />
      <meshStandardMaterial
        color={lit ? "#FFD54F" : roleColor(role)}
        emissive={lit ? "#E65C00" : "#000000"}
        emissiveIntensity={lit ? 0.35 : 0}
        roughness={0.5}
        metalness={0.3}
      />
    </mesh>
  );
}
