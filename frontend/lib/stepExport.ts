// Download a STEP file for the given frame spec from the /export/step endpoint.

import type { FrameSpec } from "@/lib/types";

function triggerDownload(filename: string, blob: Blob): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function stepFilename(spec: FrameSpec): string {
  const w = Number.isInteger(spec.width_mm)  ? spec.width_mm  : spec.width_mm;
  const d = Number.isInteger(spec.depth_mm)  ? spec.depth_mm  : spec.depth_mm;
  const h = Number.isInteger(spec.height_mm) ? spec.height_mm : spec.height_mm;
  return `frame-${w}x${d}x${h}.step`;
}

export async function downloadStepFile(spec: FrameSpec): Promise<void> {
  const resp = await fetch("/export/step", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ spec }),
  });

  if (!resp.ok) {
    const detail = await resp.json().then((j) => j.detail).catch(() => resp.statusText);
    throw new Error(String(detail));
  }

  const blob = await resp.blob();
  const filename =
    resp.headers.get("content-disposition")?.match(/filename="([^"]+)"/)?.[1] ??
    stepFilename(spec);
  triggerDownload(filename, blob);
}
