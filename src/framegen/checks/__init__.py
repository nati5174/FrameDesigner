from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from framegen.catalog import Profile
from framegen.generate import Bar
from framegen.spec import ShelfUnitSpec, TableSpec

# Named constants — changing any of these requires approval.
SAFETY_FACTOR: float = 3.0
DEFLECTION_LIMIT_DIVISOR: int = 300
_BUCKLING_K_FACTOR: float = 2.0          # K = 2.0 (fixed-free, full height)
TIPPING_HEIGHT_TO_DEPTH_LIMIT: float = 2.0

_GRAVITY: float = 9.81  # N/kg
_BBOX_EPS: float = 0.01  # mm


@dataclass(frozen=True)
class RailLoadCase:
    moment_n_mm: float
    bending_stress_mpa: float
    deflection_mm: float
    stress_passed: bool
    deflection_passed: bool
    passed: bool


@dataclass(frozen=True)
class RailCheck:
    bar_index: int
    role: str
    span_mm: float
    allowable_stress_mpa: float
    deflection_limit_mm: float
    utilisation: float  # max(σ/σ_allow, δ/δ_allow) for distributed case
    distributed: RailLoadCase
    concentrated: RailLoadCase
    passed: bool  # based on distributed case only (headline)


@dataclass(frozen=True)
class LoadEstimate:
    is_estimate: bool  # always True; present so it cannot be omitted accidentally
    safety_factor: float
    deflection_limit_fraction: int
    status: Literal["evaluated", "not_evaluated"]
    not_evaluated_reason: str | None
    governing_rail: RailCheck | None  # highest utilisation in distributed case
    all_rails: list[RailCheck]
    passed: bool


@dataclass(frozen=True)
class LegCheck:
    """Euler buckling check for shelf-unit legs.

    K = 2.0 (fixed-free) with L_eff = K × H.  Assumes the unit is anchored
    to a wall or braced against racking; not valid for a freestanding unit
    that can sway.  Compressive stress is always not_evaluated because
    cross_section_area_mm2 is not in the catalog.
    """

    is_estimate: bool           # always True
    safety_factor: float
    f_total_n: float            # N_levels × load_per_level_kg × 9.81
    f_leg_n: float              # governing leg load = F_total / 4
    k_factor: float             # 2.0
    effective_length_mm: float  # K × H
    buckling_status: Literal["evaluated", "not_evaluated"]
    buckling_not_evaluated_reason: str | None
    p_cr_n: float | None        # Euler critical load; None if not_evaluated
    p_cr_allowable_n: float | None  # P_cr / SAFETY_FACTOR; None if not_evaluated
    buckling_passed: bool
    compressive_stress_status: Literal["not_evaluated"]
    compressive_stress_reason: str
    passed: bool                # True only when buckling evaluated and passed


@dataclass(frozen=True)
class TippingCheck:
    """Rule-of-thumb tipping warning.  Does not affect CheckReport.passed."""

    h_to_d_ratio: float
    threshold: float
    warning: bool
    message: str | None         # None when warning is False


@dataclass(frozen=True)
class CollisionCheck:
    passed: bool
    colliding_pairs: list[tuple[int, int]]


@dataclass(frozen=True)
class ConnectivityCheck:
    passed: bool
    disconnected_bar_indices: list[int]


@dataclass(frozen=True)
class CheckReport:
    collision: CollisionCheck
    connectivity: ConnectivityCheck
    load: LoadEstimate
    passed: bool
    leg_check: LegCheck | None = None
    tipping: TippingCheck | None = None


# ── Geometry helpers ───────────────────────────────────────────────────────────

def _bbox(bar: Bar, P: float) -> tuple[float, float, float, float, float, float]:
    """Axis-aligned bounding box of a bar with square cross-section of side P.

    The bar has flat end faces, so its physical extent along its own axis is
    exactly [start, end].  The cross-section adds P/2 in each direction
    perpendicular to the axis only.
    """
    half = P / 2.0
    sx = min(bar.start.x, bar.end.x)
    ex = max(bar.start.x, bar.end.x)
    sy = min(bar.start.y, bar.end.y)
    ey = max(bar.start.y, bar.end.y)
    sz = min(bar.start.z, bar.end.z)
    ez = max(bar.start.z, bar.end.z)

    if ex - sx > _BBOX_EPS:
        # bar runs along X — extend cross-section in Y and Z only
        return (sx, ex, sy - half, ey + half, sz - half, ez + half)
    elif ey - sy > _BBOX_EPS:
        # bar runs along Y — extend cross-section in X and Z only
        return (sx - half, ex + half, sy, ey, sz - half, ez + half)
    else:
        # bar runs along Z (or is a point) — extend cross-section in X and Y only
        return (sx - half, ex + half, sy - half, ey + half, sz, ez)


def _overlap(a0: float, a1: float, b0: float, b1: float) -> float:
    """Signed overlap of two 1-D intervals. Negative means a gap exists."""
    return min(a1, b1) - max(a0, b0)


# ── Collision and connectivity ─────────────────────────────────────────────────

def check_collision(bars: list[Bar], profile_width_mm: float) -> CollisionCheck:
    """Flag any pair of bars whose interiors overlap (touching faces are allowed)."""
    bboxes = [_bbox(b, profile_width_mm) for b in bars]
    colliding: list[tuple[int, int]] = []
    for i in range(len(bars)):
        for j in range(i + 1, len(bars)):
            ax0, ax1, ay0, ay1, az0, az1 = bboxes[i]
            bx0, bx1, by0, by1, bz0, bz1 = bboxes[j]
            ox = _overlap(ax0, ax1, bx0, bx1)
            oy = _overlap(ay0, ay1, by0, by1)
            oz = _overlap(az0, az1, bz0, bz1)
            if ox > _BBOX_EPS and oy > _BBOX_EPS and oz > _BBOX_EPS:
                colliding.append((i, j))
    return CollisionCheck(passed=not colliding, colliding_pairs=colliding)


def check_connectivity(bars: list[Bar], profile_width_mm: float) -> ConnectivityCheck:
    """Check that every bar is reachable from bar 0 via shared faces."""
    if not bars:
        return ConnectivityCheck(passed=True, disconnected_bar_indices=[])

    bboxes = [_bbox(b, profile_width_mm) for b in bars]
    n = len(bars)
    adj: list[list[int]] = [[] for _ in range(n)]

    for i in range(n):
        for j in range(i + 1, n):
            ax0, ax1, ay0, ay1, az0, az1 = bboxes[i]
            bx0, bx1, by0, by1, bz0, bz1 = bboxes[j]
            ox = _overlap(ax0, ax1, bx0, bx1)
            oy = _overlap(ay0, ay1, by0, by1)
            oz = _overlap(az0, az1, bz0, bz1)
            # Adjacent: no gap in any dimension, and at least two dimensions share
            # positive overlap (a face, not just a point or edge).
            no_gap = ox >= -_BBOX_EPS and oy >= -_BBOX_EPS and oz >= -_BBOX_EPS
            pos_dims = sum(1 for o in (ox, oy, oz) if o > _BBOX_EPS)
            if no_gap and pos_dims >= 2:
                adj[i].append(j)
                adj[j].append(i)

    visited: set[int] = {0}
    stack = [0]
    while stack:
        node = stack.pop()
        for nb in adj[node]:
            if nb not in visited:
                visited.add(nb)
                stack.append(nb)

    disconnected = [i for i in range(n) if i not in visited]
    return ConnectivityCheck(
        passed=not disconnected, disconnected_bar_indices=disconnected
    )


# ── Rail check helper (shared by table and shelf-unit checks) ──────────────────

def _check_single_rail(
    bar_idx: int,
    bar: Bar,
    F: float,
    E: float,
    I_mm4: float,
    P: float,
    s_allow: float,
) -> RailCheck:
    """Compute both load cases for one rail bar.

    F is the load applied to this level (or to the table top).
    Two parallel rails in the same direction share the load equally, so
    each carries F/2 as a uniform distributed load (case a).
    """
    S = I_mm4 / (P / 2.0)
    L = bar.length_mm
    d_lim = L / DEFLECTION_LIMIT_DIVISOR

    # Case (a): distributed — each of two parallel rails carries F/2 as UDL.
    w = (F / 2.0) / L
    M_a = w * L * L / 8.0
    sig_a = M_a / S
    d_a = 5.0 * w * L**4 / (384.0 * E * I_mm4)
    dist = RailLoadCase(
        moment_n_mm=M_a,
        bending_stress_mpa=sig_a,
        deflection_mm=d_a,
        stress_passed=sig_a <= s_allow,
        deflection_passed=d_a <= d_lim,
        passed=sig_a <= s_allow and d_a <= d_lim,
    )

    # Case (b): concentrated — full load F as point force at midspan.
    M_b = F * L / 4.0
    sig_b = M_b / S
    d_b = F * L**3 / (48.0 * E * I_mm4)
    conc = RailLoadCase(
        moment_n_mm=M_b,
        bending_stress_mpa=sig_b,
        deflection_mm=d_b,
        stress_passed=sig_b <= s_allow,
        deflection_passed=d_b <= d_lim,
        passed=sig_b <= s_allow and d_b <= d_lim,
    )

    utilisation = max(sig_a / s_allow, d_a / d_lim)
    return RailCheck(
        bar_index=bar_idx,
        role=bar.role,
        span_mm=L,
        allowable_stress_mpa=s_allow,
        deflection_limit_mm=d_lim,
        utilisation=utilisation,
        distributed=dist,
        concentrated=conc,
        passed=dist.passed,
    )


# ── Table load check ───────────────────────────────────────────────────────────

def check_load(bars: list[Bar], spec: TableSpec, profile: Profile) -> LoadEstimate:
    """
    Estimate bending stress and deflection for every top rail.

    Two load cases are computed for each rail:
      (a) Distributed — two rails in the same direction share the total load as a
          uniform load (UDL). This is the headline pass/fail; it assumes the load
          is spread evenly over the top of the frame.
      (b) Concentrated — full load as a single point force at midspan of that one
          rail. Reported as a warning when it fails; it does not override the
          headline result.

    The governing rail is the one with the highest utilisation in case (a),
    where utilisation = max(σ/σ_allow, δ/δ_allow).

    Formulas:
      S [mm³]    = I / (P/2)
      σ_allow    = σ_y / SAFETY_FACTOR
      δ_allow    = L / DEFLECTION_LIMIT_DIVISOR
      (a) w      = (F/2) / L;  M = wL²/8;  σ = M/S;  δ = 5wL⁴/(384EI)
      (b)         M = FL/4;    σ = M/S;     δ = FL³/(48EI)

    Returns status="not_evaluated" if any required catalog field is missing.
    """
    missing: list[str] = []
    if profile.youngs_modulus_mpa is None:
        missing.append("youngs_modulus_mpa")
    if profile.yield_strength_mpa is None:
        missing.append("yield_strength_mpa")
    if profile.moment_of_inertia_mm4 is None:
        missing.append("moment_of_inertia_mm4")

    if missing:
        return LoadEstimate(
            is_estimate=True,
            safety_factor=SAFETY_FACTOR,
            deflection_limit_fraction=DEFLECTION_LIMIT_DIVISOR,
            status="not_evaluated",
            not_evaluated_reason=f"missing catalog field(s): {', '.join(missing)}",
            governing_rail=None,
            all_rails=[],
            passed=False,
        )

    E = profile.youngs_modulus_mpa
    sy = profile.yield_strength_mpa
    I_mm4 = profile.moment_of_inertia_mm4
    assert E is not None
    assert sy is not None
    assert I_mm4 is not None

    P = profile.profile_width_mm
    s_allow = sy / SAFETY_FACTOR
    F = spec.target_load_kg * _GRAVITY

    top_rails = [
        (i, b)
        for i, b in enumerate(bars)
        if b.role in ("top_rail_width", "top_rail_depth")
    ]

    rail_checks: list[RailCheck] = [
        _check_single_rail(bar_idx, bar, F, E, I_mm4, P, s_allow)
        for bar_idx, bar in top_rails
    ]

    governing = (
        max(rail_checks, key=lambda r: r.utilisation) if rail_checks else None
    )
    overall_passed = bool(rail_checks) and all(r.passed for r in rail_checks)

    return LoadEstimate(
        is_estimate=True,
        safety_factor=SAFETY_FACTOR,
        deflection_limit_fraction=DEFLECTION_LIMIT_DIVISOR,
        status="evaluated",
        not_evaluated_reason=None,
        governing_rail=governing,
        all_rails=rail_checks,
        passed=overall_passed,
    )


# ── Shelf-unit checks ──────────────────────────────────────────────────────────

def _check_shelf_load(
    bars: list[Bar],
    spec: ShelfUnitSpec,
    profile: Profile,
) -> LoadEstimate:
    """Level rail check for shelf units.

    Applies the same two load cases as the table check, using
    load_per_level_kg as the load F for every level.  Two parallel rails
    per direction per level share the load equally.
    """
    missing: list[str] = []
    if profile.youngs_modulus_mpa is None:
        missing.append("youngs_modulus_mpa")
    if profile.yield_strength_mpa is None:
        missing.append("yield_strength_mpa")
    if profile.moment_of_inertia_mm4 is None:
        missing.append("moment_of_inertia_mm4")

    if missing:
        return LoadEstimate(
            is_estimate=True,
            safety_factor=SAFETY_FACTOR,
            deflection_limit_fraction=DEFLECTION_LIMIT_DIVISOR,
            status="not_evaluated",
            not_evaluated_reason=f"missing catalog field(s): {', '.join(missing)}",
            governing_rail=None,
            all_rails=[],
            passed=False,
        )

    E = profile.youngs_modulus_mpa
    sy = profile.yield_strength_mpa
    I_mm4 = profile.moment_of_inertia_mm4
    assert E is not None
    assert sy is not None
    assert I_mm4 is not None

    P = profile.profile_width_mm
    s_allow = sy / SAFETY_FACTOR
    F = spec.load_per_level_kg * _GRAVITY

    level_rails = [
        (i, b)
        for i, b in enumerate(bars)
        if b.role in ("level_rail_width", "level_rail_depth")
    ]

    rail_checks: list[RailCheck] = [
        _check_single_rail(bar_idx, bar, F, E, I_mm4, P, s_allow)
        for bar_idx, bar in level_rails
    ]

    governing = (
        max(rail_checks, key=lambda r: r.utilisation) if rail_checks else None
    )
    overall_passed = bool(rail_checks) and all(r.passed for r in rail_checks)

    return LoadEstimate(
        is_estimate=True,
        safety_factor=SAFETY_FACTOR,
        deflection_limit_fraction=DEFLECTION_LIMIT_DIVISOR,
        status="evaluated",
        not_evaluated_reason=None,
        governing_rail=governing,
        all_rails=rail_checks,
        passed=overall_passed,
    )


def _check_leg_buckling(spec: ShelfUnitSpec, profile: Profile) -> LegCheck:
    """Euler buckling check for shelf-unit legs.

    P_cr = π² × E × I / (K × H)²    K = 2.0 (fixed-free, full height)
    Governing leg load = F_total / 4  (conservative for both 4- and 6-leg layouts)
    Pass condition: F_leg ≤ P_cr / SAFETY_FACTOR
    """
    E = profile.youngs_modulus_mpa
    I_mm4 = profile.moment_of_inertia_mm4

    n_levels = len(spec.level_heights_mm)
    f_total = n_levels * spec.load_per_level_kg * _GRAVITY
    f_leg = f_total / 4.0
    l_eff = _BUCKLING_K_FACTOR * spec.height_mm

    if E is None or I_mm4 is None:
        missing = [
            name
            for name, v in [
                ("youngs_modulus_mpa", E),
                ("moment_of_inertia_mm4", I_mm4),
            ]
            if v is None
        ]
        return LegCheck(
            is_estimate=True,
            safety_factor=SAFETY_FACTOR,
            f_total_n=f_total,
            f_leg_n=f_leg,
            k_factor=_BUCKLING_K_FACTOR,
            effective_length_mm=l_eff,
            buckling_status="not_evaluated",
            buckling_not_evaluated_reason=(
                f"missing catalog field(s): {', '.join(missing)}"
            ),
            p_cr_n=None,
            p_cr_allowable_n=None,
            buckling_passed=False,
            compressive_stress_status="not_evaluated",
            compressive_stress_reason="cross_section_area_mm2 not in catalog",
            passed=False,
        )

    assert E is not None
    assert I_mm4 is not None

    p_cr = math.pi**2 * E * I_mm4 / l_eff**2
    p_cr_allow = p_cr / SAFETY_FACTOR
    buckling_passed = f_leg <= p_cr_allow

    return LegCheck(
        is_estimate=True,
        safety_factor=SAFETY_FACTOR,
        f_total_n=f_total,
        f_leg_n=f_leg,
        k_factor=_BUCKLING_K_FACTOR,
        effective_length_mm=l_eff,
        buckling_status="evaluated",
        buckling_not_evaluated_reason=None,
        p_cr_n=p_cr,
        p_cr_allowable_n=p_cr_allow,
        buckling_passed=buckling_passed,
        compressive_stress_status="not_evaluated",
        compressive_stress_reason="cross_section_area_mm2 not in catalog",
        passed=buckling_passed,
    )


def _check_tipping(spec: ShelfUnitSpec) -> TippingCheck:
    """Rule-of-thumb tipping warning.  Does not affect pass/fail."""
    ratio = spec.height_mm / spec.depth_mm
    warning = ratio > TIPPING_HEIGHT_TO_DEPTH_LIMIT
    message: str | None = None
    if warning:
        message = (
            f"This unit is {ratio:.1f} times taller than it is deep. "
            "It may tip under a sideways push or uneven loading, "
            "so anchor it to a wall. "
            "This is a rule of thumb, not a structural calculation."
        )
    return TippingCheck(
        h_to_d_ratio=ratio,
        threshold=TIPPING_HEIGHT_TO_DEPTH_LIMIT,
        warning=warning,
        message=message,
    )


# ── Dispatcher ─────────────────────────────────────────────────────────────────

def run_checks(
    bars: list[Bar],
    spec: TableSpec | ShelfUnitSpec,
    profile: Profile,
) -> CheckReport:
    collision = check_collision(bars, profile.profile_width_mm)
    connectivity = check_connectivity(bars, profile.profile_width_mm)

    if isinstance(spec, ShelfUnitSpec):
        load = _check_shelf_load(bars, spec, profile)
        leg_check = _check_leg_buckling(spec, profile)
        tipping = _check_tipping(spec)
        passed = (
            collision.passed
            and connectivity.passed
            and load.passed
            and leg_check.passed
        )
        return CheckReport(
            collision=collision,
            connectivity=connectivity,
            load=load,
            passed=passed,
            leg_check=leg_check,
            tipping=tipping,
        )

    load = check_load(bars, spec, profile)
    return CheckReport(
        collision=collision,
        connectivity=connectivity,
        load=load,
        passed=collision.passed and connectivity.passed and load.passed,
    )
