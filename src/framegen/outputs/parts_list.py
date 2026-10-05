from __future__ import annotations

from dataclasses import dataclass

from framegen.catalog import JointConnector
from framegen.generate import Bar

_NON_LEG_ROLES = frozenset({
    "top_rail_width",
    "top_rail_depth",
    "shelf_rail_width",
    "shelf_rail_depth",
    "level_rail_width",
    "level_rail_depth",
})


@dataclass(frozen=True)
class PartsListRow:
    part_number: str
    description: str
    qty: int
    unit_price_usd: float
    line_total_usd: float
    source_url: str


@dataclass(frozen=True)
class PartsListResult:
    rows: tuple[PartsListRow, ...]
    hardware_cost_usd: float | None   # None when connectors absent for series
    hardware_weight_kg: float | None  # None when any part weight is missing
    hardware_priced: bool


def count_joints(bars: list[Bar]) -> int:
    """Number of rail-end joints: every non-leg bar contributes 2."""
    return sum(1 for b in bars if b.role in _NON_LEG_ROLES) * 2


def build_parts_list(
    bars: list[Bar],
    connectors: dict[str, JointConnector] | None,
    series: str,
) -> PartsListResult:
    """
    Build the hardware parts list for a frame.

    Returns rows=(), hardware_cost_usd=None, hardware_priced=False when
    connector data is unavailable for the requested series.
    """
    if connectors is None or series not in connectors:
        return PartsListResult(
            rows=(),
            hardware_cost_usd=None,
            hardware_weight_kg=None,
            hardware_priced=False,
        )

    n = count_joints(bars)
    connector = connectors[series]

    rows: list[PartsListRow] = []
    total_cost = 0.0
    total_weight = 0.0
    all_weights_known = True

    for part in connector.parts_per_joint:
        qty = part.qty_per_joint * n
        line_total = round(qty * part.unit_price_usd, 2)
        total_cost += line_total
        rows.append(PartsListRow(
            part_number=part.part_number,
            description=part.description,
            qty=qty,
            unit_price_usd=part.unit_price_usd,
            line_total_usd=line_total,
            source_url=part.source_url,
        ))
        if part.weight_kg is not None:
            total_weight += part.weight_kg * qty
        else:
            all_weights_known = False

    return PartsListResult(
        rows=tuple(rows),
        hardware_cost_usd=round(total_cost, 2),
        hardware_weight_kg=round(total_weight, 6) if all_weights_known else None,
        hardware_priced=True,
    )
