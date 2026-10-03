from __future__ import annotations

from framegen.catalog import Profile
from framegen.generate.table import Bar, Point, _bar
from framegen.spec import ShelfUnitSpec


def generate_shelf_unit(spec: ShelfUnitSpec, profile: Profile) -> list[Bar]:
    """Generate bars for a rectangular shelf-unit frame.

    Coordinate convention matches generate_table:
      Origin: outer bottom-front-left corner of the frame envelope.
      +X: width direction, +Y: depth direction, +Z: up.
      All coordinates are bar centrelines.

    Four corner legs run full height. Rails fit between legs, shortened
    by one profile width at each end. Each level's rail centreline is at
    z = level_height − P/2, so the rail top face is flush with the level
    height. level_index on each rail bar records which entry in
    spec.level_heights_mm the rail belongs to (0-based).

    When spec.centre_legs is True, two extra legs are placed at x = W/2
    and each width rail at every level is split into two half-rails of
    length (W − 3P) / 2.
    """
    P = profile.profile_width_mm
    W = spec.width_mm
    D = spec.depth_mm
    H = spec.height_mm
    pid = profile.part_number

    if W <= 2 * P:
        raise ValueError(
            f"width_mm ({W}) must exceed 2 × profile_width_mm ({2 * P})"
        )
    if D <= 2 * P:
        raise ValueError(
            f"depth_mm ({D}) must exceed 2 × profile_width_mm ({2 * P})"
        )
    if spec.centre_legs and W <= 3 * P:
        raise ValueError(
            f"centre_legs requires width_mm ({W}) > 3 × profile_width_mm ({3 * P})"
        )

    bars: list[Bar] = []

    # Four corner legs, full height
    for cx, cy in [
        (P / 2, P / 2),
        (W - P / 2, P / 2),
        (P / 2, D - P / 2),
        (W - P / 2, D - P / 2),
    ]:
        bars.append(_bar(pid, Point(cx, cy, 0.0), Point(cx, cy, H), "leg"))

    cx_mid = W / 2
    if spec.centre_legs:
        for cy in [P / 2, D - P / 2]:
            bars.append(
                _bar(pid, Point(cx_mid, cy, 0.0), Point(cx_mid, cy, H), "centre_leg")
            )

    # Rails at each level
    for level_idx, level_h in enumerate(spec.level_heights_mm):
        rail_z = level_h - P / 2

        if spec.centre_legs:
            for cy in [P / 2, D - P / 2]:
                bars.append(_bar(
                    pid,
                    Point(P, cy, rail_z),
                    Point(cx_mid - P / 2, cy, rail_z),
                    "level_rail_width",
                    level_idx,
                ))
                bars.append(_bar(
                    pid,
                    Point(cx_mid + P / 2, cy, rail_z),
                    Point(W - P, cy, rail_z),
                    "level_rail_width",
                    level_idx,
                ))
            for cx in [P / 2, W - P / 2]:
                bars.append(_bar(
                    pid,
                    Point(cx, P, rail_z),
                    Point(cx, D - P, rail_z),
                    "level_rail_depth",
                    level_idx,
                ))
        else:
            for cy in [P / 2, D - P / 2]:
                bars.append(_bar(
                    pid,
                    Point(P, cy, rail_z),
                    Point(W - P, cy, rail_z),
                    "level_rail_width",
                    level_idx,
                ))
            for cx in [P / 2, W - P / 2]:
                bars.append(_bar(
                    pid,
                    Point(cx, P, rail_z),
                    Point(cx, D - P, rail_z),
                    "level_rail_depth",
                    level_idx,
                ))

    return bars
