from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from framegen.generate import Bar


@dataclass(frozen=True)
class CutListRow:
    profile_id: str
    length_mm: float
    qty: int
    total_mm: float
    cost_usd: float | None = None
    weight_kg: float | None = None


@dataclass(frozen=True)
class CutList:
    rows: tuple[CutListRow, ...]
    total_mm: float
    total_cost_usd: float | None = None
    total_weight_kg: float | None = None


def build_cut_list(
    bars: list[Bar],
    *,
    price_per_mm: float | None = None,
    mass_per_metre_kg: float | None = None,
    cut_charge_usd: float | None = None,
) -> CutList:
    counts: defaultdict[tuple[str, float], int] = defaultdict(int)
    for bar in bars:
        counts[(bar.profile_id, bar.length_mm)] += 1

    rows: list[CutListRow] = []
    total = 0.0
    total_cost: float = 0.0
    total_weight: float = 0.0
    has_cost = price_per_mm is not None and cut_charge_usd is not None
    has_weight = mass_per_metre_kg is not None

    for (profile_id, length), qty in sorted(counts.items()):
        row_total = length * qty
        total += row_total

        row_cost: float | None = None
        if has_cost:
            row_cost = row_total * price_per_mm + qty * cut_charge_usd  # type: ignore[operator]
            total_cost += row_cost

        row_weight: float | None = None
        if has_weight:
            row_weight = row_total / 1000.0 * mass_per_metre_kg  # type: ignore[operator]
            total_weight += row_weight

        rows.append(CutListRow(
            profile_id=profile_id, length_mm=length, qty=qty,
            total_mm=row_total, cost_usd=row_cost, weight_kg=row_weight,
        ))

    return CutList(
        rows=tuple(rows),
        total_mm=total,
        total_cost_usd=total_cost if has_cost else None,
        total_weight_kg=total_weight if has_weight else None,
    )


def format_cut_list(cut_list: CutList) -> str:
    header = f"{'Profile':<12}  {'Length (mm)':>12}  {'Qty':>5}  {'Total (mm)':>12}"
    rule = "-" * len(header)
    lines: list[str] = [header, rule]
    for row in cut_list.rows:
        lines.append(
            f"{row.profile_id:<12}  {row.length_mm:>12.0f}"
            f"  {row.qty:>5}  {row.total_mm:>12.0f}"
        )
    lines.append(rule)
    lines.append(f"{'Total material':<32}  {cut_list.total_mm:>12.0f} mm")
    if cut_list.total_cost_usd is not None:
        lines.append(
            f"{'Estimated cost (bars only)':<32}  ${cut_list.total_cost_usd:>11.2f}"
        )
    if cut_list.total_weight_kg is not None:
        lines.append(
            f"{'Total weight':<32}  {cut_list.total_weight_kg:>11.2f} kg"
        )
    return "\n".join(lines)
