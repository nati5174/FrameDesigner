from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from framegen.catalog import Profile
from framegen.spec import TableSpec

Role = Literal[
    "leg",
    "top_rail_width",
    "top_rail_depth",
    "shelf_rail_width",
    "shelf_rail_depth",
    "centre_leg",
]


@dataclass(frozen=True)
class Point:
    x: float
    y: float
    z: float


@dataclass(frozen=True)
class Bar:
    profile_id: str
    start: Point
    end: Point
    length_mm: float
    role: Role


def _bar(profile_id: str, start: Point, end: Point, role: Role) -> Bar:
    length = math.dist(
        (start.x, start.y, start.z),
        (end.x, end.y, end.z),
    )
    return Bar(profile_id=profile_id, start=start, end=end, length_mm=length, role=role)


def generate_table(spec: TableSpec, profile: Profile) -> list[Bar]:
    """Generate bars for a rectangular table frame.

    Coordinate convention:
      Origin: outer bottom-front-left corner of the frame envelope.
      +X: width direction, +Y: depth direction, +Z: up.
      All coordinates are bar centrelines.

    Legs run full height. Rails fit between legs, shortened by one
    profile width at each end. Top rail top faces are flush with leg tops.

    When spec.centre_legs is True, two extra legs are placed at x = W/2
    and each width rail is split into two half-rails of length (W − 3P)/2.
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
    if H < P:
        raise ValueError(f"height_mm ({H}) must be >= profile_width_mm ({P})")
    if spec.centre_legs and W <= 3 * P:
        raise ValueError(
            f"centre_legs requires width_mm ({W}) > 3 × profile_width_mm ({3 * P})"
        )

    bars: list[Bar] = []

    # Four corner legs – centrelines at the four corners of the envelope
    for cx, cy in [
        (P / 2, P / 2),
        (W - P / 2, P / 2),
        (P / 2, D - P / 2),
        (W - P / 2, D - P / 2),
    ]:
        bars.append(_bar(pid, Point(cx, cy, 0.0), Point(cx, cy, H), "leg"))

    # Top rails – centreline at z = H − P/2 so top face is flush with leg tops
    rail_z = H - P / 2
    if spec.centre_legs:
        cx_mid = W / 2
        # Two centre legs at mid-width, front and back
        for cy in [P / 2, D - P / 2]:
            bars.append(
                _bar(pid, Point(cx_mid, cy, 0.0), Point(cx_mid, cy, H), "centre_leg")
            )
        # Width rails split at the centre leg; each half = (W − 3P) / 2
        for cy in [P / 2, D - P / 2]:
            bars.append(_bar(
                pid,
                Point(P, cy, rail_z),
                Point(cx_mid - P / 2, cy, rail_z),
                "top_rail_width",
            ))
            bars.append(_bar(
                pid,
                Point(cx_mid + P / 2, cy, rail_z),
                Point(W - P, cy, rail_z),
                "top_rail_width",
            ))
        # Depth rails unchanged
        for cx in [P / 2, W - P / 2]:
            bars.append(_bar(
                pid,
                Point(cx, P, rail_z),
                Point(cx, D - P, rail_z),
                "top_rail_depth",
            ))
    else:
        for cy in [P / 2, D - P / 2]:
            bars.append(_bar(
                pid,
                Point(P, cy, rail_z),
                Point(W - P, cy, rail_z),
                "top_rail_width",
            ))
        for cx in [P / 2, W - P / 2]:
            bars.append(_bar(
                pid,
                Point(cx, P, rail_z),
                Point(cx, D - P, rail_z),
                "top_rail_depth",
            ))

    # Shelf rails (optional)
    if spec.shelf_height_mm is not None:
        S = spec.shelf_height_mm
        if S < P:
            raise ValueError(
                f"shelf_height_mm ({S}) must be >= profile_width_mm ({P})"
            )
        if S > H - P:
            raise ValueError(
                f"shelf_height_mm ({S}) must be <= height_mm - profile_width_mm"
                f" ({H - P})"
            )
        shelf_z = S - P / 2
        if spec.centre_legs:
            cx_mid = W / 2
            for cy in [P / 2, D - P / 2]:
                bars.append(_bar(
                    pid,
                    Point(P, cy, shelf_z),
                    Point(cx_mid - P / 2, cy, shelf_z),
                    "shelf_rail_width",
                ))
                bars.append(_bar(
                    pid,
                    Point(cx_mid + P / 2, cy, shelf_z),
                    Point(W - P, cy, shelf_z),
                    "shelf_rail_width",
                ))
            for cx in [P / 2, W - P / 2]:
                bars.append(_bar(
                    pid,
                    Point(cx, P, shelf_z),
                    Point(cx, D - P, shelf_z),
                    "shelf_rail_depth",
                ))
        else:
            for cy in [P / 2, D - P / 2]:
                s, e = Point(P, cy, shelf_z), Point(W - P, cy, shelf_z)
                bars.append(_bar(pid, s, e, "shelf_rail_width"))
            for cx in [P / 2, W - P / 2]:
                s, e = Point(cx, P, shelf_z), Point(cx, D - P, shelf_z)
                bars.append(_bar(pid, s, e, "shelf_rail_depth"))

    return bars
