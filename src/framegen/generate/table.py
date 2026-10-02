from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from framegen.catalog import Profile
from framegen.spec import FrameSpec

Role = Literal[
    "leg",
    "top_rail_width",
    "top_rail_depth",
    "shelf_rail_width",
    "shelf_rail_depth",
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


def generate_table(spec: FrameSpec, profile: Profile) -> list[Bar]:
    """Generate bars for a rectangular table frame.

    Coordinate convention:
      Origin: outer bottom-front-left corner of the frame envelope.
      +X: width direction, +Y: depth direction, +Z: up.
      All coordinates are bar centrelines.

    Legs run full height. Rails fit between legs, shortened by one
    profile width at each end. Top rail top faces are flush with leg tops.
    """
    P = profile.profile_width_mm
    W = spec.width_mm
    D = spec.depth_mm
    H = spec.height_mm
    pid = profile.part_number

    if W <= 2 * P:
        raise ValueError(f"width_mm ({W}) must exceed 2 × profile_width_mm ({2 * P})")
    if D <= 2 * P:
        raise ValueError(f"depth_mm ({D}) must exceed 2 × profile_width_mm ({2 * P})")
    if H < P:
        raise ValueError(f"height_mm ({H}) must be >= profile_width_mm ({P})")

    bars: list[Bar] = []

    # Four legs – centrelines at the four corners of the envelope
    for cx, cy in [
        (P / 2, P / 2),
        (W - P / 2, P / 2),
        (P / 2, D - P / 2),
        (W - P / 2, D - P / 2),
    ]:
        bars.append(_bar(pid, Point(cx, cy, 0.0), Point(cx, cy, H), "leg"))

    # Top rails – centreline at z = H − P/2 so top face is flush with leg tops
    rail_z = H - P / 2
    for cy in [P / 2, D - P / 2]:
        bars.append(
            _bar(pid, Point(P, cy, rail_z), Point(W - P, cy, rail_z), "top_rail_width")
        )
    for cx in [P / 2, W - P / 2]:
        bars.append(
            _bar(pid, Point(cx, P, rail_z), Point(cx, D - P, rail_z), "top_rail_depth")
        )

    # Shelf rails (optional)
    if spec.shelf_height_mm is not None:
        S = spec.shelf_height_mm
        if S < P:
            raise ValueError(f"shelf_height_mm ({S}) must be >= profile_width_mm ({P})")
        if S > H - P:
            raise ValueError(
                f"shelf_height_mm ({S}) must be <= height_mm - profile_width_mm"
                f" ({H - P})"
            )
        shelf_z = S - P / 2
        for cy in [P / 2, D - P / 2]:
            s, e = Point(P, cy, shelf_z), Point(W - P, cy, shelf_z)
            bars.append(_bar(pid, s, e, "shelf_rail_width"))
        for cx in [P / 2, W - P / 2]:
            s, e = Point(cx, P, shelf_z), Point(cx, D - P, shelf_z)
            bars.append(_bar(pid, s, e, "shelf_rail_depth"))

    return bars
