/**
 * Convert a point from the frame coordinate system (Z-up) to Three.js (Y-up).
 *
 * Frame system: +X = width, +Y = depth, +Z = up.
 * Three.js:     +X = width, +Y = up,    +Z = -depth (right-hand).
 *
 * This is the single authoritative conversion. All 3D rendering code must
 * call this function rather than converting inline.
 */
export function toThree(
  x: number,
  y: number,
  z: number
): [number, number, number] {
  return [x, z, -y];
}
