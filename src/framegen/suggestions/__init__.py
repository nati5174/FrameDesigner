"""
Fix suggestions for frames that fail the load check.

This module is pure code — it never imports suggestions.rank or any LLM code.
The API layer decides whether to call rank.py based on key availability.

Table triggers:
  - distributed case fails  → target distributed pass
  - only concentrated warns → target concentrated pass

Shelf unit triggers:
  - any level rail fails   → reduce_load_per_level or centre_legs

Each candidate is verified by re-running generate + run_checks.
Only verified passes are returned. At most three candidates.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from framegen.catalog import Catalog, Profile
from framegen.checks import CheckReport, run_checks
from framegen.generate import Bar
from framegen.generate.shelf_unit import generate_shelf_unit
from framegen.generate.table import generate_table
from framegen.outputs.parts_list import PartsListResult, build_parts_list
from framegen.spec import ShelfUnitSpec, TableSpec

FixType = Literal[
    "reduce_span_width",
    "reduce_span_depth",
    "reduce_load",
    "centre_legs",
    "reduce_load_per_level",
    "cheaper_profile",
]

_SPAN_STEP_MM = 10
_LOAD_STEP_KG = 5
_GRAVITY = 9.81


@dataclass(frozen=True)
class FixCandidate:
    fix_type: FixType
    spec: TableSpec | ShelfUnitSpec
    check_report: CheckReport
    trade_off: str
    resolves: Literal["distributed", "concentrated"]
    concentrated_warning_remains: bool


def _floor_to(value: float, step: float) -> float:
    return math.floor(value / step) * step


def _l_max_distributed(
    E: float, I_mm4: float, S: float, s_allow: float, F: float
) -> float:
    l_stress = 16.0 * S * s_allow / F
    l_defl = math.sqrt(768.0 * E * I_mm4 / (1500.0 * F))
    return min(l_stress, l_defl)


def _l_max_concentrated(
    E: float, I_mm4: float, S: float, s_allow: float, F: float
) -> float:
    l_stress = 4.0 * S * s_allow / F
    l_defl = math.sqrt(48.0 * E * I_mm4 / (300.0 * F))
    return min(l_stress, l_defl)


def _verify_table(spec: TableSpec, profile: Profile) -> CheckReport | None:
    try:
        bars = generate_table(spec, profile)
    except ValueError:
        return None
    return run_checks(bars, spec, profile)


def _verify_shelf(spec: ShelfUnitSpec, profile: Profile) -> CheckReport | None:
    try:
        bars = generate_shelf_unit(spec, profile)
    except ValueError:
        return None
    return run_checks(bars, spec, profile)


def _conc_warns(report: CheckReport) -> bool:
    gov = report.load.governing_rail
    return gov is not None and not gov.concentrated.passed


# ── Table suggestions ─────────────────────────────────────────────────────────

def _suggest_table(
    spec: TableSpec,
    profile: Profile,
    check_report: CheckReport,
) -> list[FixCandidate]:
    load = check_report.load
    if load.status != "evaluated":
        return []

    dist_fails = not load.passed
    conc_warns = _conc_warns(check_report)
    if not dist_fails and not conc_warns:
        return []

    resolves: Literal["distributed", "concentrated"] = (
        "distributed" if dist_fails else "concentrated"
    )

    gov = load.governing_rail
    if gov is None:
        return []

    E = profile.youngs_modulus_mpa
    sy = profile.yield_strength_mpa
    I_mm4 = profile.moment_of_inertia_mm4
    if E is None or sy is None or I_mm4 is None:
        return []

    P = profile.profile_width_mm
    S = I_mm4 / (P / 2.0)
    s_allow = sy / 3.0
    F = spec.target_load_kg * _GRAVITY

    candidates: list[FixCandidate] = []

    # Fix A: reduce span
    if resolves == "distributed":
        l_max = _l_max_distributed(E, I_mm4, S, s_allow, F)
    else:
        l_max = _l_max_concentrated(E, I_mm4, S, s_allow, F)

    role = gov.role
    if role == "top_rail_width":
        new_dim = _floor_to(l_max + 2 * P, _SPAN_STEP_MM)
        if new_dim < spec.width_mm and new_dim > 3 * P:
            candidate_spec = spec.model_copy(update={"width_mm": new_dim})
            report = _verify_table(candidate_spec, profile)
            if report is not None and (
                (resolves == "distributed" and report.load.passed) or
                (resolves == "concentrated" and not _conc_warns(report))
            ):
                candidates.append(FixCandidate(
                    fix_type="reduce_span_width",
                    spec=candidate_spec,
                    check_report=report,
                    trade_off=(
                        f"Narrow the frame to {new_dim:.0f} mm wide"
                        f" (from {spec.width_mm:.0f} mm)."
                    ),
                    resolves=resolves,
                    concentrated_warning_remains=_conc_warns(report),
                ))
    elif role == "top_rail_depth":
        new_dim = _floor_to(l_max + 2 * P, _SPAN_STEP_MM)
        if new_dim < spec.depth_mm:
            candidate_spec = spec.model_copy(update={"depth_mm": new_dim})
            report = _verify_table(candidate_spec, profile)
            if report is not None and (
                (resolves == "distributed" and report.load.passed) or
                (resolves == "concentrated" and not _conc_warns(report))
            ):
                candidates.append(FixCandidate(
                    fix_type="reduce_span_depth",
                    spec=candidate_spec,
                    check_report=report,
                    trade_off=(
                        f"Reduce the depth to {new_dim:.0f} mm"
                        f" (from {spec.depth_mm:.0f} mm)."
                    ),
                    resolves=resolves,
                    concentrated_warning_remains=_conc_warns(report),
                ))

    # Fix B: reduce load
    u = gov.utilisation if resolves == "distributed" else max(
        gov.concentrated.bending_stress_mpa / gov.allowable_stress_mpa,
        gov.concentrated.deflection_mm / gov.deflection_limit_mm,
    )
    if u > 0:
        new_load = _floor_to(spec.target_load_kg / u, _LOAD_STEP_KG)
        if new_load > 0 and new_load < spec.target_load_kg:
            candidate_spec = spec.model_copy(update={"target_load_kg": new_load})
            report = _verify_table(candidate_spec, profile)
            if report is not None and (
                (resolves == "distributed" and report.load.passed) or
                (resolves == "concentrated" and not _conc_warns(report))
            ):
                candidates.append(FixCandidate(
                    fix_type="reduce_load",
                    spec=candidate_spec,
                    check_report=report,
                    trade_off=(
                        f"Reduce the target load to {new_load:.0f} kg"
                        f" (from {spec.target_load_kg:.0f} kg)."
                    ),
                    resolves=resolves,
                    concentrated_warning_remains=_conc_warns(report),
                ))

    # Fix C: centre legs
    if not spec.centre_legs and spec.width_mm > 3 * P:
        candidate_spec = spec.model_copy(update={"centre_legs": True})
        report = _verify_table(candidate_spec, profile)
        if report is not None and (
            (resolves == "distributed" and report.load.passed) or
            (resolves == "concentrated" and not _conc_warns(report))
        ):
            candidates.append(FixCandidate(
                fix_type="centre_legs",
                spec=candidate_spec,
                check_report=report,
                trade_off="Add a centre pair of legs, halving the width span.",
                resolves=resolves,
                concentrated_warning_remains=_conc_warns(report),
            ))

    return candidates[:3]


# ── Shelf unit suggestions ────────────────────────────────────────────────────

def _suggest_shelf(
    spec: ShelfUnitSpec,
    profile: Profile,
    check_report: CheckReport,
) -> list[FixCandidate]:
    load = check_report.load
    if load.status != "evaluated":
        return []
    leg = check_report.leg_check
    if load.passed and (leg is None or leg.passed):
        return []

    gov = load.governing_rail
    if not load.passed and gov is None:
        return []

    E = profile.youngs_modulus_mpa
    sy = profile.yield_strength_mpa
    I_mm4 = profile.moment_of_inertia_mm4
    if E is None or sy is None or I_mm4 is None:
        return []

    candidates: list[FixCandidate] = []

    # Fix A: reduce load per level
    if not load.passed and gov is not None:
        u = gov.utilisation
        if u > 0:
            new_load = _floor_to(spec.load_per_level_kg / u, _LOAD_STEP_KG)
            if new_load > 0 and new_load < spec.load_per_level_kg:
                candidate_spec = spec.model_copy(
                    update={"load_per_level_kg": new_load}
                )
                report = _verify_shelf(candidate_spec, profile)
                if report is not None and report.load.passed:
                    candidates.append(FixCandidate(
                        fix_type="reduce_load_per_level",
                        spec=candidate_spec,
                        check_report=report,
                        trade_off=(
                            f"Reduce the load per level to {new_load:.0f} kg"
                            f" (from {spec.load_per_level_kg:.0f} kg)."
                        ),
                        resolves="distributed",
                        concentrated_warning_remains=_conc_warns(report),
                    ))

    # Fix B: centre legs (halves width span)
    P = profile.profile_width_mm
    if not spec.centre_legs and spec.width_mm > 3 * P:
        candidate_spec = spec.model_copy(update={"centre_legs": True})
        report = _verify_shelf(candidate_spec, profile)
        if report is not None and report.load.passed:
            candidates.append(FixCandidate(
                fix_type="centre_legs",
                spec=candidate_spec,
                check_report=report,
                trade_off="Add a centre pair of legs, halving the width span.",
                resolves="distributed",
                concentrated_warning_remains=_conc_warns(report),
            ))

    return candidates[:3]


# ── Cheaper-profile suggestion ────────────────────────────────────────────────

def _build_cost(
    bars: list[Bar],
    price_per_mm: float,
    cut_charge_usd: float,
) -> float:
    total_mm: float = sum(b.length_mm for b in bars)
    n_cuts = len({(b.profile_id, b.length_mm) for b in bars})
    return total_mm * price_per_mm + n_cuts * cut_charge_usd


def suggest_cheaper_profile(
    spec: TableSpec | ShelfUnitSpec,
    profile: Profile,
    check_report: CheckReport,
    catalog: Catalog,
    *,
    current_parts: PartsListResult | None = None,
) -> FixCandidate | None:
    """
    If the frame already passes and a cheaper profile also passes,
    return a FixCandidate for switching profiles.  Returns None otherwise.

    When current_parts is supplied and both the current and candidate profiles
    have hardware priced, total_cost (bars + hardware) is used for comparison
    and reported in the trade-off string.  Otherwise bars-only cost is used.
    """
    if not check_report.passed:
        return None

    current_price = profile.price_per_mm
    if current_price is None:
        return None

    cut_charge = catalog.cut_charge_usd or 0.0
    current_conc_warn = _conc_warns(check_report)

    # Collect cheaper profiles by bars price_per_mm, sorted ascending
    cheaper: list[Profile] = sorted(
        (
            p for p in catalog.profiles.values()
            if p.series != profile.series
            and p.price_per_mm is not None
            and p.price_per_mm < current_price
        ),
        key=lambda p: p.price_per_mm or 0.0,
    )

    for alt in cheaper:
        alt_series = alt.series
        alt_spec = spec.model_copy(update={"profile_series": alt_series})
        try:
            if isinstance(alt_spec, ShelfUnitSpec):
                alt_bars = generate_shelf_unit(alt_spec, alt)
            else:
                alt_bars = generate_table(alt_spec, alt)
        except ValueError:
            continue

        alt_report = run_checks(alt_bars, alt_spec, alt)
        if not alt_report.passed:
            continue

        alt_conc_warn = _conc_warns(alt_report)
        introduces_conc_warn = alt_conc_warn and not current_conc_warn

        # Compute cost saving
        try:
            if isinstance(spec, ShelfUnitSpec):
                cur_bars = generate_shelf_unit(spec, profile)
            else:
                cur_bars = generate_table(spec, profile)
            cur_bars_cost = _build_cost(cur_bars, current_price, cut_charge)
            alt_bars_cost = _build_cost(alt_bars, alt.price_per_mm, cut_charge)  # type: ignore[arg-type]

            # Use total cost (bars + hardware) when both profiles have hardware data
            alt_parts = build_parts_list(alt_bars, catalog.connectors, alt_series)
            use_total = (
                current_parts is not None
                and current_parts.hardware_priced
                and alt_parts.hardware_priced
                and current_parts.hardware_cost_usd is not None
                and alt_parts.hardware_cost_usd is not None
            )
            if use_total and current_parts is not None:
                cur_total = cur_bars_cost + current_parts.hardware_cost_usd  # type: ignore[operator]
                alt_total = alt_bars_cost + alt_parts.hardware_cost_usd  # type: ignore[operator]
                saving = cur_total - alt_total
                cost_label = "total"
            else:
                saving = cur_bars_cost - alt_bars_cost
                cost_label = "bars"

            if introduces_conc_warn:
                trade_off = (
                    f"Switch to {alt_series} (saves ~${saving:.2f} on {cost_label}). "
                    f"Note: introduces a concentrated-load warning not present "
                    f"on the current design."
                )
            else:
                trade_off = (
                    f"Switch to {alt_series} and save ~${saving:.2f} on {cost_label}."
                )
        except ValueError:
            trade_off = f"Switch to {alt_series} for lower cost."

        return FixCandidate(
            fix_type="cheaper_profile",
            spec=alt_spec,
            check_report=alt_report,
            trade_off=trade_off,
            resolves="distributed",
            concentrated_warning_remains=introduces_conc_warn,
        )

    return None


# ── Public entry point ────────────────────────────────────────────────────────

def suggest_fixes(
    spec: TableSpec | ShelfUnitSpec,
    profile: Profile,
    check_report: CheckReport,
) -> list[FixCandidate]:
    """
    Return up to three verified fix candidates for the given spec and report.
    Returns [] when the frame is fully healthy.
    """
    if isinstance(spec, ShelfUnitSpec):
        candidates = _suggest_shelf(spec, profile, check_report)
    else:
        candidates = _suggest_table(spec, profile, check_report)

    return candidates
