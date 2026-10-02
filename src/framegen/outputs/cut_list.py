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


@dataclass(frozen=True)
class CutList:
    rows: tuple[CutListRow, ...]
    total_mm: float


def build_cut_list(bars: list[Bar]) -> CutList:
    counts: defaultdict[tuple[str, float], int] = defaultdict(int)
    for bar in bars:
        counts[(bar.profile_id, bar.length_mm)] += 1

    rows: list[CutListRow] = []
    total = 0.0
    for (profile_id, length), qty in sorted(counts.items()):
        row_total = length * qty
        total += row_total
        rows.append(CutListRow(
            profile_id=profile_id, length_mm=length, qty=qty, total_mm=row_total
        ))

    return CutList(rows=tuple(rows), total_mm=total)


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
    return "\n".join(lines)
