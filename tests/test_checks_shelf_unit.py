from __future__ import annotations

import pytest

from framegen.catalog import Profile
from framegen.checks import (
    SAFETY_FACTOR,
    TIPPING_HEIGHT_TO_DEPTH_LIMIT,
    _check_leg_buckling,
    _check_shelf_load,
    _check_tipping,
    run_checks,
)
from framegen.generate.shelf_unit import generate_shelf_unit
from framegen.spec import ShelfUnitSpec

# ── Helpers ───────────────────────────────────────────────────────────────────
# Worked example: 900 × 400 × 1800 mm, 4 levels, 30 kg/level, 40-series.
#   P = 40  → width rail span = 820 mm, depth rail span = 320 mm
#   F_level = 30 × 9.81 = 294.3 N
#
# Governing rail (width, L = 820 mm):
#   S = 137870 / 20 = 6893.5 mm³
#   σ_allow = 172.37 / 3 = 57.457 MPa
#   δ_allow = 820 / 300 = 2.733 mm
#
# Case (a) distributed: w = (F/2)/L = 0.17945 N/mm
#   σ = 2.188 MPa,  δ = 0.111 mm  (both pass)
#
# Case (b) concentrated: M = F×L/4 = 60 331 N·mm
#   σ = 8.752 MPa,  δ = 0.356 mm  (both pass)
#
# Leg check: L_eff = 2 × 1800 = 3600 mm
#   P_cr = π² × E × I / L_eff² = 7239 N
#   P_cr_allow = 7239 / 3 = 2413 N;  F_leg = 1177.2 / 4 = 294.3 N  (passes)
#
# Tipping: H/D = 1800/400 = 4.5  (warning; does not affect passed)


def _profile() -> Profile:
    return Profile(
        part_number="40-4040",
        series="40-series",
        profile_width_mm=40.0,
        alloy="6063-T6",
        youngs_modulus_mpa=68947.6,
        yield_strength_mpa=172.37,
        moment_of_inertia_mm4=137870.0,
        source="80/20",
        source_url="https://8020.net/40-4040.html",
    )


def _bare_profile() -> Profile:
    return Profile(
        part_number="40-4040",
        series="40-series",
        profile_width_mm=40.0,
        source="80/20",
        source_url="https://8020.net/40-4040.html",
    )


def _spec(**overrides: object) -> ShelfUnitSpec:
    defaults: dict[str, object] = dict(
        frame_type="shelf_unit",
        width_mm=900.0,
        depth_mm=400.0,
        height_mm=1800.0,
        profile_series="40-series",
        level_heights_mm=[450.0, 900.0, 1350.0, 1800.0],
        load_per_level_kg=30.0,
    )
    defaults.update(overrides)
    return ShelfUnitSpec.model_validate(defaults)


# ── Shelf load — governing rail ────────────────────────────────────────────────

def test_shelf_load_status_evaluated() -> None:
    bars = generate_shelf_unit(_spec(), _profile())
    result = _check_shelf_load(bars, _spec(), _profile())
    assert result.status == "evaluated"
    assert result.is_estimate is True


def test_shelf_load_governing_is_width_rail() -> None:
    bars = generate_shelf_unit(_spec(), _profile())
    result = _check_shelf_load(bars, _spec(), _profile())
    gov = result.governing_rail
    assert gov is not None
    assert gov.role == "level_rail_width"
    assert gov.span_mm == pytest.approx(820.0)


def test_shelf_load_allowable_stress() -> None:
    bars = generate_shelf_unit(_spec(), _profile())
    result = _check_shelf_load(bars, _spec(), _profile())
    assert result.governing_rail is not None
    assert result.governing_rail.allowable_stress_mpa == pytest.approx(
        172.37 / 3.0, abs=0.001
    )


def test_shelf_load_deflection_limit() -> None:
    bars = generate_shelf_unit(_spec(), _profile())
    result = _check_shelf_load(bars, _spec(), _profile())
    assert result.governing_rail is not None
    assert result.governing_rail.deflection_limit_mm == pytest.approx(
        820.0 / 300.0, abs=0.001
    )


def test_shelf_load_distributed_stress() -> None:
    bars = generate_shelf_unit(_spec(), _profile())
    result = _check_shelf_load(bars, _spec(), _profile())
    assert result.governing_rail is not None
    assert result.governing_rail.distributed.bending_stress_mpa == pytest.approx(
        2.188, abs=0.001
    )


def test_shelf_load_distributed_deflection() -> None:
    bars = generate_shelf_unit(_spec(), _profile())
    result = _check_shelf_load(bars, _spec(), _profile())
    assert result.governing_rail is not None
    assert result.governing_rail.distributed.deflection_mm == pytest.approx(
        0.111, abs=0.001
    )


def test_shelf_load_distributed_passes() -> None:
    bars = generate_shelf_unit(_spec(), _profile())
    result = _check_shelf_load(bars, _spec(), _profile())
    assert result.governing_rail is not None
    assert result.governing_rail.distributed.passed is True
    assert result.passed is True


def test_shelf_load_utilisation() -> None:
    bars = generate_shelf_unit(_spec(), _profile())
    result = _check_shelf_load(bars, _spec(), _profile())
    assert result.governing_rail is not None
    assert result.governing_rail.utilisation == pytest.approx(0.0407, abs=0.0002)


# ── Shelf load — concentrated case ────────────────────────────────────────────

def test_shelf_concentrated_stress() -> None:
    bars = generate_shelf_unit(_spec(), _profile())
    result = _check_shelf_load(bars, _spec(), _profile())
    assert result.governing_rail is not None
    assert result.governing_rail.concentrated.bending_stress_mpa == pytest.approx(
        8.752, abs=0.001
    )


def test_shelf_concentrated_deflection() -> None:
    bars = generate_shelf_unit(_spec(), _profile())
    result = _check_shelf_load(bars, _spec(), _profile())
    assert result.governing_rail is not None
    assert result.governing_rail.concentrated.deflection_mm == pytest.approx(
        0.356, abs=0.001
    )


def test_shelf_concentrated_passes() -> None:
    bars = generate_shelf_unit(_spec(), _profile())
    result = _check_shelf_load(bars, _spec(), _profile())
    assert result.governing_rail is not None
    assert result.governing_rail.concentrated.passed is True


# ── Shelf load — missing catalog fields ───────────────────────────────────────

def test_shelf_load_missing_fields_not_evaluated() -> None:
    bars = generate_shelf_unit(_spec(), _bare_profile())
    result = _check_shelf_load(bars, _spec(), _bare_profile())
    assert result.status == "not_evaluated"
    assert result.passed is False
    assert result.not_evaluated_reason is not None
    assert "moment_of_inertia_mm4" in result.not_evaluated_reason


# ── Leg check ─────────────────────────────────────────────────────────────────

def test_leg_check_loads() -> None:
    result = _check_leg_buckling(_spec(), _profile())
    assert result.f_total_n == pytest.approx(4 * 30.0 * 9.81, abs=0.01)
    assert result.f_leg_n == pytest.approx(4 * 30.0 * 9.81 / 4.0, abs=0.01)


def test_leg_check_k_factor() -> None:
    result = _check_leg_buckling(_spec(), _profile())
    assert result.k_factor == pytest.approx(2.0)


def test_leg_check_effective_length() -> None:
    result = _check_leg_buckling(_spec(), _profile())
    assert result.effective_length_mm == pytest.approx(2.0 * 1800.0)


def test_leg_check_p_cr() -> None:
    result = _check_leg_buckling(_spec(), _profile())
    assert result.p_cr_n == pytest.approx(7239.0, abs=1.0)


def test_leg_check_p_cr_allowable() -> None:
    result = _check_leg_buckling(_spec(), _profile())
    assert result.p_cr_allowable_n is not None
    assert result.p_cr_allowable_n == pytest.approx(
        result.p_cr_n / SAFETY_FACTOR, rel=1e-6  # type: ignore[operator]
    )


def test_leg_check_buckling_passes() -> None:
    result = _check_leg_buckling(_spec(), _profile())
    assert result.buckling_status == "evaluated"
    assert result.buckling_passed is True
    assert result.passed is True


def test_leg_check_compressive_stress_not_evaluated() -> None:
    result = _check_leg_buckling(_spec(), _profile())
    assert result.compressive_stress_status == "not_evaluated"
    assert result.compressive_stress_reason is not None
    assert "cross_section_area_mm2" in result.compressive_stress_reason


def test_leg_check_missing_fields_not_evaluated() -> None:
    result = _check_leg_buckling(_spec(), _bare_profile())
    assert result.buckling_status == "not_evaluated"
    assert result.p_cr_n is None
    assert result.p_cr_allowable_n is None
    assert result.passed is False


# ── Tipping check ─────────────────────────────────────────────────────────────

def test_tipping_ratio() -> None:
    result = _check_tipping(_spec())
    assert result.h_to_d_ratio == pytest.approx(4.5)


def test_tipping_threshold() -> None:
    result = _check_tipping(_spec())
    assert result.threshold == pytest.approx(TIPPING_HEIGHT_TO_DEPTH_LIMIT)


def test_tipping_warning_issued() -> None:
    result = _check_tipping(_spec())
    assert result.warning is True
    assert result.message is not None
    assert "4.5" in result.message
    assert "anchor it to a wall" in result.message


def test_tipping_no_warning_when_within_limit() -> None:
    # H/D = 600/400 = 1.5 < 2.0
    result = _check_tipping(
        _spec(height_mm=600.0, level_heights_mm=[200.0, 400.0, 600.0])
    )
    assert result.warning is False
    assert result.message is None


def test_tipping_does_not_affect_passed() -> None:
    # Even with tipping warning, run_checks.passed is still True when load checks pass
    profile = _profile()
    bars = generate_shelf_unit(_spec(), profile)
    report = run_checks(bars, _spec(), profile)
    assert report.tipping is not None
    assert report.tipping.warning is True
    assert report.passed is True   # tipping doesn't block pass


# ── run_checks dispatch ────────────────────────────────────────────────────────

def test_run_checks_returns_leg_check() -> None:
    profile = _profile()
    bars = generate_shelf_unit(_spec(), profile)
    report = run_checks(bars, _spec(), profile)
    assert report.leg_check is not None


def test_run_checks_returns_tipping() -> None:
    profile = _profile()
    bars = generate_shelf_unit(_spec(), profile)
    report = run_checks(bars, _spec(), profile)
    assert report.tipping is not None


def test_run_checks_overall_passes() -> None:
    profile = _profile()
    bars = generate_shelf_unit(_spec(), profile)
    report = run_checks(bars, _spec(), profile)
    assert report.passed is True
    assert report.collision.passed is True
    assert report.connectivity.passed is True
    assert report.load.passed is True
    assert report.leg_check is not None and report.leg_check.passed is True
