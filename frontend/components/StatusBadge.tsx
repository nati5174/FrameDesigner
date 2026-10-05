/**
 * Status badge derived directly from API fields — no frontend calculations.
 *
 * Logic:
 *   check_report.passed == false               → Fail
 *   load.passed == true AND concentrated fails → Pass with warning
 *   load.passed == true AND concentrated passes→ Pass
 */
import type { CheckReport } from "@/lib/types";

interface StatusBadgeProps {
  checkReport: CheckReport;
}

type Status = "pass" | "warn" | "fail";

function deriveStatus(cr: CheckReport): Status {
  if (!cr.passed) return "fail";
  const gov = cr.load.governing_rail;
  if (gov && !gov.concentrated.passed) return "warn";
  return "pass";
}

const CONFIG: Record<Status, { label: string; icon: string; classes: string }> = {
  pass: {
    label: "Pass",
    icon: "✓",
    classes: "bg-pass/10 text-pass border-pass/30",
  },
  warn: {
    label: "Pass with warning",
    icon: "⚠",
    classes: "bg-warn-bg text-warn border-warn/30",
  },
  fail: {
    label: "Fail",
    icon: "✕",
    classes: "bg-fail/10 text-fail border-fail/30",
  },
};

export function StatusBadge({ checkReport }: StatusBadgeProps) {
  const status = deriveStatus(checkReport);
  const { label, icon, classes } = CONFIG[status];
  return (
    <span
      aria-label={`Load check: ${label}`}
      className={`inline-flex items-center gap-1.5 rounded border px-3 py-1 text-sm font-medium ${classes}`}
    >
      <span aria-hidden="true">{icon}</span>
      {label}
    </span>
  );
}
