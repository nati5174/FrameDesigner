from __future__ import annotations

import pytest

from framegen.catalog import Profile
from framegen.checks import check_collision, check_connectivity, check_load
from framegen.generate import Bar, Point, generate_table
from framegen.spec import TableSpec

# ── Helpers ───────────────────────────────────────────────────────────────────

def _full_profile() -> Profile:
    """Profile with all load-check fields populated (catalog-v2 values)."""
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
    """Profile without load-check fields (as in catalog-v1)."""
    return Profile(
        part_number="40-4040",
        series="40-series",
        profile_width_mm=40.0,
        source="80/20",
        source_url="https://8020.net/40-4040.html",
    )


def _spec(**overrides: object) -> TableSpec:
    defaults: dict[str, object] = dict(
        frame_type="table",
        width_mm=1500.0,
        depth_mm=700.0,
        height_mm=900.0,
        profile_series="40-series",
        target_load_kg=100.0,
    )
    defaults.update(overrides)
    return TableSpec.model_validate(defaults)


# ── Load estimate — worked example numbers ────────────────────────────────────
# 1500 × 700 × 900 mm table, 100 kg load, 40-4040 profile.
# Governing rail: width rails, span 1420 mm.
#
# Derived values:
#   S = 137870 / 20 = 6893.5 mm³
#   σ_allow = 172.37 / 3.0 = 57.457 MPa
#   δ_allow = 1420 / 300 = 4.733 mm
#   F = 100 × 9.81 = 981 N
#
# Case (a) distributed:
#   w = (981/2) / 1420 = 0.34542 N/mm
#   M = wL²/8 = 87 064 N·mm  →  σ = 12.63 MPa
#   δ = 5wL⁴/(384EI) = 1.92 mm
#
# Case (b) concentrated:
#   M = 981×1420/4 = 348 255 N·mm  →  σ = 50.52 MPa  (passes)
#   δ = FL³/(48EI) = 6.16 mm                          (fails: > 4.73)

def test_load_estimate_status_evaluated() -> None:
    bars = generate_table(_spec(), _full_profile())
    result = check_load(bars, _spec(), _full_profile())
    assert result.status == "evaluated"
    assert result.is_estimate is True


def test_load_governing_rail_is_width_rail() -> None:
    bars = generate_table(_spec(), _full_profile())
    result = check_load(bars, _spec(), _full_profile())
    gov = result.governing_rail
    assert gov is not None
    assert gov.role == "top_rail_width"
    assert gov.span_mm == pytest.approx(1420.0)


def test_distributed_bending_stress() -> None:
    bars = generate_table(_spec(), _full_profile())
    result = check_load(bars, _spec(), _full_profile())
    assert result.governing_rail is not None
    assert result.governing_rail.distributed.bending_stress_mpa == pytest.approx(
        12.63, abs=0.01
    )


def test_distributed_deflection() -> None:
    bars = generate_table(_spec(), _full_profile())
    result = check_load(bars, _spec(), _full_profile())
    assert result.governing_rail is not None
    assert result.governing_rail.distributed.deflection_mm == pytest.approx(
        1.92, abs=0.01
    )


def test_distributed_case_passes() -> None:
    bars = generate_table(_spec(), _full_profile())
    result = check_load(bars, _spec(), _full_profile())
    assert result.governing_rail is not None
    assert result.governing_rail.distributed.passed is True
    assert result.passed is True


def test_concentrated_bending_stress() -> None:
    bars = generate_table(_spec(), _full_profile())
    result = check_load(bars, _spec(), _full_profile())
    assert result.governing_rail is not None
    assert result.governing_rail.concentrated.bending_stress_mpa == pytest.approx(
        50.52, abs=0.01
    )


def test_concentrated_deflection() -> None:
    bars = generate_table(_spec(), _full_profile())
    result = check_load(bars, _spec(), _full_profile())
    assert result.governing_rail is not None
    assert result.governing_rail.concentrated.deflection_mm == pytest.approx(
        6.16, abs=0.01
    )


def test_concentrated_stress_passes_deflection_fails() -> None:
    bars = generate_table(_spec(), _full_profile())
    result = check_load(bars, _spec(), _full_profile())
    assert result.governing_rail is not None
    conc = result.governing_rail.concentrated
    assert conc.stress_passed is True
    assert conc.deflection_passed is False


# ── Load estimate — missing catalog value ─────────────────────────────────────

def test_missing_catalog_value_not_evaluated() -> None:
    bars = generate_table(_spec(), _bare_profile())
    result = check_load(bars, _spec(), _bare_profile())
    assert result.status == "not_evaluated"


def test_missing_catalog_value_never_passes() -> None:
    bars = generate_table(_spec(), _bare_profile())
    result = check_load(bars, _spec(), _bare_profile())
    assert result.passed is False


def test_missing_catalog_value_names_the_fields() -> None:
    bars = generate_table(_spec(), _bare_profile())
    result = check_load(bars, _spec(), _bare_profile())
    assert result.not_evaluated_reason is not None
    assert "moment_of_inertia_mm4" in result.not_evaluated_reason


# ── Collision check ───────────────────────────────────────────────────────────

def test_no_collision_for_valid_table() -> None:
    profile = _full_profile()
    bars = generate_table(_spec(), profile)
    result = check_collision(bars, profile.profile_width_mm)
    assert result.passed is True
    assert result.colliding_pairs == []


def test_collision_detected() -> None:
    P = 40.0
    # Two vertical bars 25 mm apart centre-to-centre (< P=40), volumes overlap.
    # b0 bbox x: [0, 40];  b1 bbox x: [5, 45]  →  overlap x = 35 mm > EPS
    b0 = Bar("40-4040", Point(20.0, 20.0, 0.0), Point(20.0, 20.0, 900.0), 900.0, "leg")
    b1 = Bar("40-4040", Point(25.0, 20.0, 0.0), Point(25.0, 20.0, 900.0), 900.0, "leg")
    result = check_collision([b0, b1], P)
    assert result.passed is False
    assert (0, 1) in result.colliding_pairs


def test_touching_bars_not_a_collision() -> None:
    P = 40.0
    # Rail end flush with leg face: overlap in x is exactly 0 (touching, not colliding).
    leg = Bar("40-4040", Point(20.0, 20.0, 0.0), Point(20.0, 20.0, 900.0), 900.0, "leg")
    # Rail centreline at x = 60 (= P + P/2), y = 20, z = 860.
    # Rail bbox x: [60 - 20, 60 + 940] — wait, the rail spans along x.
    # Leg bbox x: [0, 40]. Rail starts at x=40 (leg face), so rail bbox x: [40, 1460].
    # Overlap x = min(40,1460) - max(0,40) = 40-40 = 0 → not a collision.
    rail = Bar(
        "40-4040",
        Point(40.0, 20.0, 860.0),
        Point(1460.0, 20.0, 860.0),
        1420.0,
        "top_rail_width",
    )
    result = check_collision([leg, rail], P)
    assert result.passed is True
    assert result.colliding_pairs == []


# ── Connectivity check ────────────────────────────────────────────────────────

def test_connected_for_valid_table() -> None:
    profile = _full_profile()
    bars = generate_table(_spec(), profile)
    result = check_connectivity(bars, profile.profile_width_mm)
    assert result.passed is True
    assert result.disconnected_bar_indices == []


def test_disconnected_bar_detected() -> None:
    profile = _full_profile()
    bars = list(generate_table(_spec(), profile))
    # Append a bar far from the frame — no shared face with any existing bar.
    isolated = Bar(
        "40-4040",
        Point(5000.0, 5000.0, 0.0),
        Point(5000.0, 5000.0, 900.0),
        900.0,
        "leg",
    )
    bars_with_isolated = bars + [isolated]
    result = check_connectivity(bars_with_isolated, profile.profile_width_mm)
    assert result.passed is False
    assert len(bars) in result.disconnected_bar_indices
