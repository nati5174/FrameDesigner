"""
Fix suggestions for frames that fail the load check.

This module is pure code — it never imports suggestions.rank or any LLM code.
The API layer decides whether to call rank.py based on key availability.

Trigger:
  - distributed case fails  → target distributed pass
  - only concentrated warns → target concentrated pass

Each candidate is verified by running generate_table + run_checks.
Only verified passes are returned. At most three candidates.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from framegen.catalog import Profile
from framegen.checks import CheckReport, run_checks
from framegen.generate.table import generate_table
from framegen.spec import TableSpec

FixType = Literal[
    "reduce_span_width",
    "reduce_span_depth",
    "reduce_load",
    "centre_legs",
]

# Rounding increments
_SPAN_STEP_MM = 10      # round candidate dimensions down to nearest 10 mm
_LOAD_STEP_KG = 5       # round candidate load down to nearest 5 kg
_GRAVITY = 9.81


@dataclass(frozen=True)
class FixCandidate:
    fix_type: FixType
    spec: TableSpec
    check_report: CheckReport
    trade_off: str          # template text; rank.py may replace this
    resolves: Literal["distributed", "concentrated"]
    concentrated_warning_remains: bool


def _floor_to(value: float, step: float) -> float:
    return math.floor(value / step) * step


def _l_max_distributed(
    E: float, I_mm4: float, S: float, s_allow: float, F: float
) -> float:
    """Largest span (mm) at which the distributed case just passes."""
    l_stress = 16.0 * S * s_allow / F
    l_defl = math.sqrt(768.0 * E * I_mm4 / (1500.0 * F))
    return min(l_stress, l_defl)


def _l_max_concentrated(
    E: float, I_mm4: float, S: float, s_allow: float, F: float
) -> float:
    """Largest span (mm) at which the concentrated case just passes."""
    l_stress = 4.0 * S * s_allow / F
    l_defl = math.sqrt(48.0 * E * I_mm4 / (300.0 * F))
    return min(l_stress, l_defl)


def _verify(spec: TableSpec, profile: Profile) -> CheckReport | None:
    """Return CheckReport if generate succeeds, else None."""
    try:
        bars = generate_table(spec, profile)
    except ValueError:
        return None
    return run_checks(bars, spec, profile)


def _conc_warns(report: CheckReport) -> bool:
    gov = report.load.governing_rail
    return gov is not None and not gov.concentrated.passed


def suggest_fixes(
    spec: TableSpec,
    profile: Profile,
    check_report: CheckReport,
) -> list[FixCandidate]:
    """
    Return up to three verified fix candidates.

    Called only when check_report.load.passed is False OR the concentrated
    case warns. Returns [] when the frame is fully healthy.
    """
    load = check_report.load
    if load.status != "evaluated":
        return []

    # Decide target
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

    # ── Fix A: reduce span ────────────────────────────────────────────────────
    if resolves == "distributed":
        l_max = _l_max_distributed(E, I_mm4, S, s_allow, F)
    else:
        l_max = _l_max_concentrated(E, I_mm4, S, s_allow, F)

    role = gov.role  # "top_rail_width" or "top_rail_depth"
    if role == "top_rail_width":
        new_dim = _floor_to(l_max + 2 * P, _SPAN_STEP_MM)
        if new_dim < spec.width_mm and new_dim > 3 * P:
            candidate_spec = spec.model_copy(update={"width_mm": new_dim})
            report = _verify(candidate_spec, profile)
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
            report = _verify(candidate_spec, profile)
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

    # ── Fix B: reduce load ────────────────────────────────────────────────────
    u = gov.utilisation if resolves == "distributed" else max(
        gov.concentrated.bending_stress_mpa / gov.allowable_stress_mpa,
        gov.concentrated.deflection_mm / gov.deflection_limit_mm,
    )
    if u > 0:
        new_load = _floor_to(spec.target_load_kg / u, _LOAD_STEP_KG)
        if new_load > 0 and new_load < spec.target_load_kg:
            candidate_spec = spec.model_copy(update={"target_load_kg": new_load})
            report = _verify(candidate_spec, profile)
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

    # ── Fix C: centre legs ────────────────────────────────────────────────────
    if not spec.centre_legs and spec.width_mm > 3 * P:
        candidate_spec = spec.model_copy(update={"centre_legs": True})
        report = _verify(candidate_spec, profile)
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
