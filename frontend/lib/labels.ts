// Shared display-label helpers — keeps internal API identifiers out of the UI.

const ROLE_LABELS: Record<string, string> = {
  top_rail_width:    "Top rail, width direction",
  top_rail_depth:    "Top rail, depth direction",
  bottom_rail_width: "Bottom rail, width direction",
  bottom_rail_depth: "Bottom rail, depth direction",
  level_rail_width:  "Level rail, width direction",
  level_rail_depth:  "Level rail, depth direction",
  shelf_rail_width:  "Shelf rail, width direction",
  shelf_rail_depth:  "Shelf rail, depth direction",
  leg:               "Leg",
  centre_leg:        "Centre leg",
  shelf_leg:         "Shelf leg",
};

export function formatRole(role: string): string {
  return ROLE_LABELS[role] ?? role.replace(/_/g, " ");
}

export function formatFrameType(raw: string): string {
  if (raw === "shelf_unit") return "Shelf unit";
  if (raw === "table") return "Table";
  return raw;
}

/** USD amount with thousands separator and exactly 2 decimal places. */
export function usd(amount: number): string {
  return amount.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}
